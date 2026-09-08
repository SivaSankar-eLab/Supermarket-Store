"""
Concurrency stress test — THE PROOF.

Fires N simultaneous finalize_bill calls against a product with M units.
Only M calls should succeed. The rest must get INSUFFICIENT_STOCK.
Final qty_on_hand must be exactly 0.

This test is the key differentiator: a PROOF rather than a claim.
Results are printed in a formatted table for pasting into README.md.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field

import pytest

from tests.conftest import create_test_product


INITIAL_STOCK = 20     # units available
CONCURRENT_CALLS = 50  # simultaneous finalize_bill calls


@dataclass
class ConcurrencyResult:
    total: int = 0
    succeeded: int = 0
    failed_insufficient: int = 0
    failed_other: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    final_qty: float = 0.0


async def _make_one_bill(product_id: str, call_num: int) -> dict:
    """Create a separate draft bill and attempt to finalize it."""
    from app.tools.billing import start_bill, add_bill_item, finalize_bill

    # Each call gets its own DRAFT bill (1 unit each)
    bill = (await start_bill())["data"]["bill"]
    bill_id = bill["id"]
    await add_bill_item(bill_id, product_id, 1.0)
    result = await finalize_bill(
        bill_id=bill_id,
        payment_mode="CASH",
        idempotency_key=f"concurrent-test-{call_num}-{uuid.uuid4().hex[:8]}",
    )
    return result


@pytest.mark.asyncio
async def test_concurrent_finalize_correctness():
    """
    STRESS TEST: 50 simultaneous finalize_bill calls on a product with 20 units.

    Expected:
      - Exactly 20 succeed
      - Exactly 30 return INSUFFICIENT_STOCK
      - Final qty_on_hand == 0 (never negative)
    """
    from app.tools.inventory import get_stock

    # Create product with exactly INITIAL_STOCK units
    product = await create_test_product(
        name="Concurrent Test Product",
        qty_on_hand=float(INITIAL_STOCK),
    )
    pid = product["id"]

    start = time.perf_counter()

    # Fire all concurrent calls
    tasks = [_make_one_bill(pid, i) for i in range(CONCURRENT_CALLS)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    duration_ms = (time.perf_counter() - start) * 1000

    # Tally results
    cr = ConcurrencyResult(total=CONCURRENT_CALLS, duration_ms=duration_ms)
    for r in results:
        if isinstance(r, Exception):
            cr.failed_other += 1
            cr.errors.append(str(r))
        elif r.get("ok"):
            cr.succeeded += 1
        elif r.get("error_code") == "INSUFFICIENT_STOCK":
            cr.failed_insufficient += 1
        else:
            cr.failed_other += 1
            cr.errors.append(r.get("message", "unknown error"))

    # Check final stock
    stock_result = await get_stock(pid)
    cr.final_qty = stock_result["data"]["product"]["qty_on_hand"]

    # ── Print proof table ─────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  CONCURRENCY STRESS TEST RESULTS")
    print("═" * 60)
    print(f"  Initial stock:        {INITIAL_STOCK} units")
    print(f"  Concurrent calls:     {CONCURRENT_CALLS}")
    print(f"  Duration:             {duration_ms:.1f} ms")
    print("─" * 60)
    print(f"  ✅ Succeeded:         {cr.succeeded}")
    print(f"  ❌ INSUFFICIENT_STOCK:{cr.failed_insufficient}")
    print(f"  ⚠️  Other errors:      {cr.failed_other}")
    print("─" * 60)
    print(f"  Final qty_on_hand:   {cr.final_qty}")
    print("═" * 60)

    if cr.errors:
        print("\nOther errors:")
        for e in cr.errors[:5]:
            print(f"  • {e}")

    # ── Assertions ────────────────────────────────────────────────────────────
    assert cr.failed_other == 0, (
        f"Unexpected errors during concurrent test: {cr.errors}"
    )
    assert cr.succeeded == INITIAL_STOCK, (
        f"Expected exactly {INITIAL_STOCK} successes, got {cr.succeeded}. "
        "Race condition detected!"
    )
    assert cr.failed_insufficient == CONCURRENT_CALLS - INITIAL_STOCK, (
        f"Expected {CONCURRENT_CALLS - INITIAL_STOCK} INSUFFICIENT_STOCK errors, "
        f"got {cr.failed_insufficient}"
    )
    assert cr.final_qty == 0.0, (
        f"Final stock is {cr.final_qty}, not 0! "
        "Either stock went negative or some succeeded when it shouldn't have."
    )

    print("\n✅ ALL ASSERTIONS PASSED — Concurrency correctness verified!")


@pytest.mark.asyncio
async def test_concurrent_finalize_stock_never_negative():
    """
    Even under extreme concurrency, qty_on_hand must never drop below zero.
    This test is a canary for deadlock regressions.
    """
    from app.tools.inventory import get_stock

    product = await create_test_product(
        name="Zero Floor Test",
        qty_on_hand=5.0,
    )
    pid = product["id"]

    # Fire 20 calls against a product with only 5 units
    tasks = [_make_one_bill(pid, i + 1000) for i in range(20)]
    await asyncio.gather(*tasks, return_exceptions=True)

    stock = await get_stock(pid)
    final_qty = stock["data"]["product"]["qty_on_hand"]

    assert final_qty >= 0.0, (
        f"CRITICAL: qty_on_hand went negative! Got {final_qty}. "
        "SELECT FOR UPDATE deadlock prevention has failed."
    )
    assert final_qty == 0.0, (
        f"Expected 0 (5 successes of 20), got {final_qty}"
    )


@pytest.mark.asyncio
async def test_concurrent_credit_balance_integrity():
    """
    Concurrent credit additions must all be recorded and balance must be sum of all.
    """
    from app.tools.credit import add_customer, add_credit, get_customer_balance

    customer = (await add_customer("Concurrent Credit Customer", "9999999901"))["data"]["customer"]
    cid = customer["id"]

    CREDIT_AMOUNT = 100.0
    NUM_CREDITS = 20

    tasks = [add_credit(cid, CREDIT_AMOUNT) for _ in range(NUM_CREDITS)]
    results = await asyncio.gather(*tasks)

    all_ok = all(r["ok"] for r in results)
    assert all_ok, "Some credit additions failed"

    balance_result = await get_customer_balance(cid)
    balance = balance_result["data"]["balance"]
    expected = CREDIT_AMOUNT * NUM_CREDITS

    assert balance == expected, (
        f"Balance mismatch! Expected {expected}, got {balance}. "
        "Concurrent writes to credit ledger are incorrect."
    )
