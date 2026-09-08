"""
KiranaBot — Analytics Tools

Daily close, sales summary, and GST reports.
All computations run in Postgres — no Python-side aggregation for correctness.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Bill, BillItem, Product, CreditTransaction, Customer
from app.tools import ok, err
from app.config import get_settings

settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)


def _parse_date(d: str | None) -> date:
    if d is None:
        return date.today()
    try:
        return date.fromisoformat(d)
    except ValueError:
        raise ValueError(f"Invalid date format: {d}. Use YYYY-MM-DD.")


# ── Tool: daily_close ──────────────────────────────────────────────────────────

async def daily_close(target_date: str | None = None) -> dict[str, Any]:
    """
    Generate a daily close report: revenue, GST collected, top products, payment breakdown.

    Args:
        target_date: Date in YYYY-MM-DD format (defaults to today)

    Returns: ok({report: {...}})
    """
    try:
        d = _parse_date(target_date)
    except ValueError as e:
        return err("INVALID_DATE", str(e))

    async with get_db() as db:
        # Revenue and GST totals
        totals_result = await db.execute(
            select(
                func.count(Bill.id).label("bill_count"),
                func.coalesce(func.sum(Bill.subtotal), 0).label("total_subtotal"),
                func.coalesce(func.sum(Bill.cgst_total), 0).label("total_cgst"),
                func.coalesce(func.sum(Bill.sgst_total), 0).label("total_sgst"),
                func.coalesce(func.sum(Bill.grand_total), 0).label("total_revenue"),
            ).where(
                Bill.shop_id == SHOP_ID,
                Bill.status == "FINALIZED",
                func.date(Bill.finalized_at) == d,
            )
        )
        totals = totals_result.one()

        # Payment mode breakdown
        payment_result = await db.execute(
            select(
                Bill.payment_mode,
                func.count(Bill.id).label("count"),
                func.sum(Bill.grand_total).label("amount"),
            ).where(
                Bill.shop_id == SHOP_ID,
                Bill.status == "FINALIZED",
                func.date(Bill.finalized_at) == d,
            ).group_by(Bill.payment_mode)
        )
        payment_breakdown = [
            {
                "mode": row.payment_mode or "UNKNOWN",
                "count": row.count,
                "amount": float(row.amount or 0),
            }
            for row in payment_result.all()
        ]

        # Top 5 products by revenue
        top_products_result = await db.execute(
            text("""
                SELECT p.name, p.brand, p.unit,
                       SUM(bi.qty) as total_qty,
                       SUM(bi.line_total) as total_revenue
                FROM bill_items bi
                JOIN bills b ON bi.bill_id = b.id
                JOIN products p ON bi.product_id = p.id
                WHERE b.shop_id = :shop_id
                  AND b.status = 'FINALIZED'
                  AND DATE(b.finalized_at) = :d
                GROUP BY p.id, p.name, p.brand, p.unit
                ORDER BY total_revenue DESC
                LIMIT 5
            """),
            {"shop_id": SHOP_ID, "d": d},
        )
        top_products = [
            {
                "name": f"{row.brand} {row.name}".strip() if row.brand else row.name,
                "qty_sold": float(row.total_qty),
                "unit": row.unit,
                "revenue": float(row.total_revenue),
            }
            for row in top_products_result.all()
        ]

        # Credit ledger transactions today
        credit_today_result = await db.execute(
            select(func.coalesce(func.sum(CreditTransaction.amount), 0))
            .join(Customer, CreditTransaction.customer_id == Customer.id)
            .where(
                Customer.shop_id == SHOP_ID,
                CreditTransaction.type == "CREDIT",
                func.date(CreditTransaction.created_at) == d,
            )
        )
        credit_today = float(credit_today_result.scalar() or 0)

        return ok({
            "date": str(d),
            "summary": {
                "bills_count": totals.bill_count,
                "total_revenue": float(totals.total_revenue),
                "total_subtotal": float(totals.total_subtotal),
                "total_cgst": float(totals.total_cgst),
                "total_sgst": float(totals.total_sgst),
                "total_gst": float((totals.total_cgst or 0) + (totals.total_sgst or 0)),
                "credit_today": credit_today,
                "khata_credit_today": credit_today,
                "cash_revenue": next(
                    (p["amount"] for p in payment_breakdown if p["mode"] == "CASH"), 0
                ),
            },
            "payment_breakdown": payment_breakdown,
            "top_products": top_products,
            "message": (
                f"📊 {d}: {totals.bill_count} bills | "
                f"Revenue ₹{float(totals.total_revenue):.2f} | "
                f"GST ₹{float((totals.total_cgst or 0) + (totals.total_sgst or 0)):.2f}"
            ),
        })


# ── Tool: sales_summary ────────────────────────────────────────────────────────

async def sales_summary(period: str = "week") -> dict[str, Any]:
    """
    Sales summary for a given period.

    Args:
        period: "today" | "week" | "month" | "year"

    Returns: ok({summary: {...}, daily_breakdown: [...]})
    """
    today = date.today()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=6)
    elif period == "month":
        start_date = today.replace(day=1)
    elif period == "year":
        start_date = today.replace(month=1, day=1)
    else:
        return err("INVALID_PERIOD", "period must be: today | week | month | year")

    async with get_db() as db:
        # Overall totals
        totals_result = await db.execute(
            select(
                func.count(Bill.id).label("bill_count"),
                func.coalesce(func.sum(Bill.grand_total), 0).label("revenue"),
                func.coalesce(func.sum(Bill.cgst_total + Bill.sgst_total), 0).label("gst"),
            ).where(
                Bill.shop_id == SHOP_ID,
                Bill.status == "FINALIZED",
                func.date(Bill.finalized_at) >= start_date,
                func.date(Bill.finalized_at) <= today,
            )
        )
        totals = totals_result.one()

        # Daily breakdown
        daily_result = await db.execute(
            text("""
                SELECT DATE(finalized_at) as day,
                       COUNT(id) as bills,
                       COALESCE(SUM(grand_total), 0) as revenue
                FROM bills
                WHERE shop_id = :shop_id
                  AND status = 'FINALIZED'
                  AND DATE(finalized_at) >= :start
                  AND DATE(finalized_at) <= :end
                GROUP BY day
                ORDER BY day
            """),
            {"shop_id": SHOP_ID, "start": start_date, "end": today},
        )
        daily = [
            {
                "date": str(row.day),
                "bills": row.bills,
                "revenue": float(row.revenue),
            }
            for row in daily_result.all()
        ]

        avg_daily = float(totals.revenue) / max(len(daily), 1)

        return ok({
            "period": period,
            "start_date": str(start_date),
            "end_date": str(today),
            "totals": {
                "bills": totals.bill_count,
                "revenue": float(totals.revenue),
                "gst_collected": float(totals.gst),
                "avg_daily_revenue": round(avg_daily, 2),
                "avg_bill_value": round(
                    float(totals.revenue) / max(totals.bill_count, 1), 2
                ),
            },
            "daily_breakdown": daily,
        })


# ── Tool: gst_collected ────────────────────────────────────────────────────────

async def gst_collected(
    period: str = "month",
    by_slab: bool = True,
) -> dict[str, Any]:
    """
    GST collection report, optionally broken down by GST slab.

    Args:
        period: "today" | "week" | "month" | "year"
        by_slab: If True, show CGST+SGST per GST slab (default True)

    Returns: ok({gst_report: {...}})
    """
    today = date.today()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=6)
    elif period == "month":
        start_date = today.replace(day=1)
    elif period == "year":
        start_date = today.replace(month=1, day=1)
    else:
        return err("INVALID_PERIOD", "period must be: today | week | month | year")

    async with get_db() as db:
        if by_slab:
            slab_result = await db.execute(
                text("""
                    SELECT bi.gst_slab,
                           SUM(bi.taxable_value) as taxable,
                           SUM(bi.cgst_amt) as cgst,
                           SUM(bi.sgst_amt) as sgst
                    FROM bill_items bi
                    JOIN bills b ON bi.bill_id = b.id
                    WHERE b.shop_id = :shop_id
                      AND b.status = 'FINALIZED'
                      AND DATE(b.finalized_at) >= :start
                      AND DATE(b.finalized_at) <= :end
                    GROUP BY bi.gst_slab
                    ORDER BY bi.gst_slab
                """),
                {"shop_id": SHOP_ID, "start": start_date, "end": today},
            )
            slabs = [
                {
                    "slab": float(row.gst_slab),
                    "taxable_value": float(row.taxable or 0),
                    "cgst": float(row.cgst or 0),
                    "sgst": float(row.sgst or 0),
                    "total_gst": float((row.cgst or 0) + (row.sgst or 0)),
                }
                for row in slab_result.all()
            ]
        else:
            slabs = []

        # Overall GST totals
        total_result = await db.execute(
            select(
                func.coalesce(func.sum(Bill.cgst_total), 0).label("total_cgst"),
                func.coalesce(func.sum(Bill.sgst_total), 0).label("total_sgst"),
                func.coalesce(func.sum(Bill.subtotal), 0).label("total_taxable"),
                func.count(Bill.id).label("bill_count"),
            ).where(
                Bill.shop_id == SHOP_ID,
                Bill.status == "FINALIZED",
                func.date(Bill.finalized_at) >= start_date,
                func.date(Bill.finalized_at) <= today,
            )
        )
        total = total_result.one()

        return ok({
            "period": period,
            "start_date": str(start_date),
            "end_date": str(today),
            "gst_report": {
                "total_taxable_value": float(total.total_taxable),
                "total_cgst": float(total.total_cgst),
                "total_sgst": float(total.total_sgst),
                "total_gst_collected": float(total.total_cgst + total.total_sgst),
                "bills_count": total.bill_count,
            },
            "by_slab": slabs,
        })


# ── Tool: reorder_suggestions (Sales Velocity Based) ───────────────────────────

async def reorder_suggestions(lookback_days: int = 14, lead_time_days: int = 3) -> dict[str, Any]:
    """
    Calculate sales velocity (units/day) for each product over the lookback window
    and suggest reorder quantities to avoid stockouts based on supplier lead time.

    Args:
        lookback_days: Number of historical days to calculate sales velocity (default 14)
        lead_time_days: Supplier delivery lead time in days (default 3)

    Returns: ok({suggestions: [...]})
    """
    today = date.today()
    start_date = today - timedelta(days=lookback_days)

    async with get_db() as db:
        # Query total units sold per product over the lookback period
        velocity_result = await db.execute(
            text("""
                SELECT p.id, p.name, p.brand, p.unit, p.qty_on_hand, p.reorder_level,
                       COALESCE(SUM(bi.qty), 0) as total_sold
                FROM products p
                LEFT JOIN bill_items bi ON p.id = bi.product_id
                LEFT JOIN bills b ON bi.bill_id = b.id 
                     AND b.status = 'FINALIZED' 
                     AND DATE(b.finalized_at) >= :start_date
                WHERE p.shop_id = :shop_id AND p.is_active = true
                GROUP BY p.id, p.name, p.brand, p.unit, p.qty_on_hand, p.reorder_level
                ORDER BY p.name ASC
            """),
            {"shop_id": SHOP_ID, "start_date": start_date},
        )

        suggestions = []
        for row in velocity_result.all():
            qty_on_hand = float(row.qty_on_hand)
            total_sold = float(row.total_sold)
            daily_velocity = round(total_sold / max(lookback_days, 1), 2)
            
            # Days of stock left at current velocity
            days_of_stock = round(qty_on_hand / daily_velocity, 1) if daily_velocity > 0 else 999.0
            
            # Reorder threshold: lead time demand + safety stock (reorder_level)
            safety_stock = float(row.reorder_level)
            lead_time_demand = daily_velocity * lead_time_days
            recommended_reorder_point = round(lead_time_demand + safety_stock, 2)
            
            needs_reorder = (qty_on_hand <= recommended_reorder_point) or (qty_on_hand <= safety_stock)
            
            # Suggested order quantity: 7 days of forward demand + safety stock shortfall
            suggested_order_qty = max(0.0, round((daily_velocity * 7) + (recommended_reorder_point - qty_on_hand), 2)) if needs_reorder else 0.0

            if needs_reorder or daily_velocity > 0:
                suggestions.append({
                    "product_id": str(row.id),
                    "product_name": f"{row.brand} {row.name}".strip() if row.brand else row.name,
                    "unit": row.unit,
                    "current_stock": qty_on_hand,
                    "daily_sales_velocity": daily_velocity,
                    "days_of_inventory_left": days_of_stock,
                    "needs_reorder": needs_reorder,
                    "suggested_order_qty": suggested_order_qty,
                    "urgency": "CRITICAL" if qty_on_hand <= 0 else ("HIGH" if days_of_stock <= lead_time_days else ("MEDIUM" if needs_reorder else "LOW")),
                })

        suggestions.sort(key=lambda s: (0 if s["urgency"] == "CRITICAL" else (1 if s["urgency"] == "HIGH" else (2 if s["urgency"] == "MEDIUM" else 3)), s["days_of_inventory_left"]))

        return ok({
            "lookback_days": lookback_days,
            "lead_time_days": lead_time_days,
            "total_skus_analyzed": len(suggestions),
            "reorder_needed_count": sum(1 for s in suggestions if s["needs_reorder"]),
            "suggestions": suggestions,
        })

