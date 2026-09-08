"""
KiranaBot — PreToolUse and PostToolUse Hooks

Hooks provide a SECOND, INDEPENDENT guardrail layer:
  - PreToolUse: fires BEFORE the tool function runs
  - PostToolUse: fires AFTER and handles logging/metrics

The sell-below-cost guard in PreToolUse is completely independent of
the same check inside finalize_bill — defense in depth.
"""
from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ── PreToolUse Hook ───────────────────────────────────────────────────────────

async def pre_tool_use_hook(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """
    Called BEFORE any tool executes.

    Returns:
      - None to allow the tool call to proceed normally
      - A dict with {"block": True, "message": "..."} to abort the call
        and return the message to the agent instead

    Current guards:
      1. finalize_bill: re-compute aggregate cost from DB, block if selling at a loss
      2. void_bill: require non-empty reason
      3. adjust_stock: require non-empty reason
    """
    if tool_name == "finalize_bill":
        return await _guard_finalize_bill(tool_input)

    if tool_name == "void_bill":
        reason = tool_input.get("reason", "").strip()
        if not reason:
            return {
                "block": True,
                "result": {
                    "ok": False,
                    "error_code": "REASON_REQUIRED",
                    "message": "A reason is required to void a bill. "
                               "Example: 'Customer returned goods'",
                },
            }

    if tool_name == "adjust_stock":
        reason = tool_input.get("reason", "").strip()
        if not reason:
            return {
                "block": True,
                "result": {
                    "ok": False,
                    "error_code": "REASON_REQUIRED",
                    "message": "A reason is required for stock adjustments. "
                               "Example: 'Damaged in transit' or 'Physical count mismatch'",
                },
            }

    return None  # Allow the call


async def _guard_finalize_bill(tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """
    Independent pre-check for finalize_bill:
    1. Bill must have at least one item
    2. Grand total must not be below aggregate cost

    This runs BEFORE the tool function's own identical checks.
    If this hook fires but the tool doesn't (or vice versa), both still catch it.
    """
    from app.database import get_db
    from app.models import Bill, BillItem, Product
    from app.tools.gst_utils import compute_gst_line, compute_bill_totals

    bill_id_str = tool_input.get("bill_id")
    if not bill_id_str:
        return None  # Let the tool handle the missing arg error

    try:
        bill_id = uuid.UUID(bill_id_str)
    except ValueError:
        return None

    try:
        async with get_db() as db:
            bill = await db.get(Bill, bill_id)
            if not bill or bill.status != "DRAFT":
                return None  # Let tool handle

            items_result = await db.execute(
                select(BillItem).where(BillItem.bill_id == bill_id)
            )
            items = items_result.scalars().all()
            if not items:
                return None  # Let tool handle empty-bill error

            aggregate_cost = Decimal("0")
            gst_lines = []
            for item in items:
                product = await db.get(Product, item.product_id)
                if not product:
                    continue
                aggregate_cost += product.cost_price * item.qty
                gst_line = compute_gst_line(item.qty, product.sell_price, product.gst_slab)
                gst_lines.append(gst_line)

            if not gst_lines:
                return None

            totals = compute_bill_totals(gst_lines)
            if totals.grand_total < aggregate_cost:
                return {
                    "block": True,
                    "result": {
                        "ok": False,
                        "error_code": "SELL_BELOW_COST",
                        "message": (
                            f"🛑 Hook blocked finalize_bill: grand total "
                            f"₹{float(totals.grand_total):.2f} is below aggregate cost "
                            f"₹{float(aggregate_cost):.2f}. "
                            "Adjust prices before finalizing."
                        ),
                        "grand_total": float(totals.grand_total),
                        "aggregate_cost": float(aggregate_cost),
                    },
                }
    except Exception as exc:
        logger.warning("pre_tool_use_hook error (allowing through): %s", exc)

    return None  # Allow


# ── PostToolUse Hook ──────────────────────────────────────────────────────────

_tool_start_times: dict[str, float] = {}


def pre_tool_timing(tool_name: str, call_id: str) -> None:
    """Record start time for latency measurement."""
    _tool_start_times[call_id] = time.perf_counter()


async def post_tool_use_hook(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_result: dict[str, Any],
    call_id: str = "",
) -> None:
    """
    Called AFTER every tool completes.
    Logs tool name, latency, and success/failure for observability.
    """
    elapsed_ms = 0.0
    if call_id and call_id in _tool_start_times:
        elapsed_ms = (time.perf_counter() - _tool_start_times.pop(call_id)) * 1000

    success = tool_result.get("ok", True)
    error_code = tool_result.get("error_code", "")

    log_msg = (
        f"TOOL {tool_name} | "
        f"{'OK' if success else 'ERR:' + error_code} | "
        f"{elapsed_ms:.1f}ms"
    )

    if success:
        logger.info(log_msg)
    else:
        logger.warning(log_msg + f" | input_keys={list(tool_input.keys())}")

    # Future: push to metrics/telemetry here
