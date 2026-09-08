"""
KiranaBot — Billing Tools

The finalize_bill function is the most critical path in the entire system:
  1. SELECT FOR UPDATE on all products (ordered by product_id to prevent deadlock)
  2. Hard check qty_on_hand >= requested for every item
  3. Compute GST per line using Decimal arithmetic
  4. Verify grand_total > aggregate cost (sell-below-cost guard)
  5. Update stock, insert movements, mark bill FINALIZED
  6. Idempotency: if idempotency_key already exists, return cached result

All business rules live HERE, in code — not in the system prompt.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Bill, BillItem, Product, StockMovement, Customer
from app.tools import ok, err
from app.tools.gst_utils import compute_gst_line, compute_bill_totals
from app.config import get_settings

settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _bill_to_dict(bill: Bill, items: list[BillItem] | None = None) -> dict:
    d = {
        "id": str(bill.id),
        "status": bill.status,
        "customer_id": str(bill.customer_id) if bill.customer_id else None,
        "payment_mode": bill.payment_mode,
        "payment_ref": bill.payment_ref,
        "subtotal": float(bill.subtotal) if bill.subtotal else None,
        "cgst_total": float(bill.cgst_total) if bill.cgst_total else None,
        "sgst_total": float(bill.sgst_total) if bill.sgst_total else None,
        "round_off": float(bill.round_off) if bill.round_off else None,
        "grand_total": float(bill.grand_total) if bill.grand_total else None,
        "created_at": bill.created_at.isoformat() if bill.created_at else None,
        "finalized_at": bill.finalized_at.isoformat() if bill.finalized_at else None,
    }
    if items is not None:
        d["items"] = [_item_to_dict(i) for i in items]
    return d


from sqlalchemy import select, func, inspect

def _item_to_dict(item: BillItem, product_name: str | None = None) -> dict:
    p_name = product_name
    if not p_name:
        try:
            insp = inspect(item)
            if "product" in insp.dict and insp.dict["product"] is not None:
                p_name = insp.dict["product"].display_name
            else:
                p_name = str(item.product_id)
        except Exception:
            p_name = str(item.product_id)

    return {
        "id": str(item.id),
        "product_id": str(item.product_id),
        "product_name": p_name,
        "qty": float(item.qty),
        "unit_price": float(item.unit_price),
        "gst_slab": float(item.gst_slab),
        "taxable_value": float(item.taxable_value) if item.taxable_value else None,
        "cgst_amt": float(item.cgst_amt) if item.cgst_amt else None,
        "sgst_amt": float(item.sgst_amt) if item.sgst_amt else None,
        "line_total": float(item.line_total) if item.line_total else None,
    }


# ── Tool: start_bill ──────────────────────────────────────────────────────────

async def start_bill(customer_id: str | None = None) -> dict[str, Any]:
    """
    Create a new DRAFT bill. The bill stays in DRAFT until finalize_bill is called.
    Stock is NOT touched at this stage.

    Args:
        customer_id: UUID of customer (optional — pass None for walk-in customers)

    Returns: ok({bill: {...}}) with the new bill ID
    """
    async with get_db() as db:
        if customer_id:
            cust = await db.get(Customer, uuid.UUID(customer_id))
            if not cust or cust.shop_id != SHOP_ID:
                return err("CUSTOMER_NOT_FOUND", f"Customer {customer_id} not found.")

        bill = Bill(
            shop_id=SHOP_ID,
            customer_id=uuid.UUID(customer_id) if customer_id else None,
            status="DRAFT",
        )
        db.add(bill)
        await db.flush()
        return ok({
            "bill": _bill_to_dict(bill),
            "message": f"✅ New bill started. ID: {bill.id}. Add items with add_bill_item.",
        })


# ── Tool: add_bill_item ────────────────────────────────────────────────────────

async def add_bill_item(
    bill_id: str,
    product_id: str,
    qty: float,
) -> dict[str, Any]:
    """
    Add a product to a DRAFT bill. GST is computed immediately.
    Stock is NOT deducted until finalize_bill.

    Args:
        bill_id: UUID of the DRAFT bill
        product_id: UUID of the product (use find_product first)
        qty: Quantity to add

    Returns: ok({item: {...}, bill_preview: {...}}) or err
    """
    if qty <= 0:
        return err("INVALID_QTY", "Quantity must be greater than zero.")

    async with get_db() as db:
        # Load bill
        bill = await db.get(Bill, uuid.UUID(bill_id))
        if not bill or bill.shop_id != SHOP_ID:
            return err("BILL_NOT_FOUND", f"Bill {bill_id} not found.")
        if bill.status != "DRAFT":
            return err(
                "BILL_NOT_DRAFT",
                f"Bill {bill_id} is {bill.status}. Only DRAFT bills can be edited.",
            )

        # Load product
        product = await db.get(Product, uuid.UUID(product_id))
        if not product or product.shop_id != SHOP_ID:
            return err("PRODUCT_NOT_FOUND", f"Product {product_id} not found.")

        # Warn (but don't block) if stock is insufficient
        qty_dec = Decimal(str(qty))
        insufficient_warning = None
        if product.qty_on_hand < qty_dec:
            insufficient_warning = (
                f"⚠️ Warning: Only {float(product.qty_on_hand)} {product.unit} "
                f"in stock. Finalization will fail if stock isn't restocked."
            )

        # Compute GST
        gst_line = compute_gst_line(qty_dec, product.sell_price, product.gst_slab)

        # Check if product already in bill — if so, update qty
        existing_result = await db.execute(
            select(BillItem).where(
                BillItem.bill_id == uuid.UUID(bill_id),
                BillItem.product_id == uuid.UUID(product_id),
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update existing item
            existing.qty = gst_line.qty
            existing.taxable_value = gst_line.taxable_value
            existing.cgst_amt = gst_line.cgst_amt
            existing.sgst_amt = gst_line.sgst_amt
            existing.line_total = gst_line.line_total
            item = existing
            action = "Updated"
        else:
            item = BillItem(
                bill_id=uuid.UUID(bill_id),
                product_id=product.id,
                qty=gst_line.qty,
                unit_price=product.sell_price,
                gst_slab=product.gst_slab,
                taxable_value=gst_line.taxable_value,
                cgst_amt=gst_line.cgst_amt,
                sgst_amt=gst_line.sgst_amt,
                line_total=gst_line.line_total,
            )
            db.add(item)
            action = "Added"

        await db.flush()
        result = {
            "action": action,
            "item": _item_to_dict(item),
            "product_name": product.display_name,
        }
        if insufficient_warning:
            result["warning"] = insufficient_warning
        return ok(result)


# ── Tool: update_bill_item ─────────────────────────────────────────────────────

async def update_bill_item(item_id: str, qty: float) -> dict[str, Any]:
    """
    Update the quantity of an item in a DRAFT bill. Recalculates GST in place.

    Args:
        item_id: UUID of the bill item to update
        qty: New quantity (must be > 0; use remove_bill_item to delete)

    Returns: ok({item: {...}}) or err
    """
    if qty <= 0:
        return err("INVALID_QTY", "Quantity must be > 0. Use remove_bill_item to delete.")

    async with get_db() as db:
        item_result = await db.execute(
            select(BillItem).where(BillItem.id == uuid.UUID(item_id))
        )
        item = item_result.scalar_one_or_none()
        if not item:
            return err("ITEM_NOT_FOUND", f"Bill item {item_id} not found.")

        bill = await db.get(Bill, item.bill_id)
        if bill.status != "DRAFT":
            return err("BILL_NOT_DRAFT", "Cannot edit a finalized or voided bill.")

        gst_line = compute_gst_line(Decimal(str(qty)), item.unit_price, item.gst_slab)
        item.qty = gst_line.qty
        item.taxable_value = gst_line.taxable_value
        item.cgst_amt = gst_line.cgst_amt
        item.sgst_amt = gst_line.sgst_amt
        item.line_total = gst_line.line_total

        await db.flush()
        return ok({"item": _item_to_dict(item), "message": "✅ Item quantity updated."})


# ── Tool: remove_bill_item ─────────────────────────────────────────────────────

async def remove_bill_item(item_id: str) -> dict[str, Any]:
    """
    Remove an item from a DRAFT bill entirely.

    Args:
        item_id: UUID of the bill item to remove

    Returns: ok({message: ...}) or err
    """
    async with get_db() as db:
        item_result = await db.execute(
            select(BillItem).where(BillItem.id == uuid.UUID(item_id))
        )
        item = item_result.scalar_one_or_none()
        if not item:
            return err("ITEM_NOT_FOUND", f"Bill item {item_id} not found.")

        bill = await db.get(Bill, item.bill_id)
        if bill.status != "DRAFT":
            return err("BILL_NOT_DRAFT", "Cannot edit a finalized or voided bill.")

        await db.delete(item)
        return ok({"message": "✅ Item removed from bill."})


# ── Tool: get_draft_bill ───────────────────────────────────────────────────────

async def get_draft_bill(bill_id: str) -> dict[str, Any]:
    """
    Get the current state of a bill (draft or finalized) with all items and GST totals.

    Args:
        bill_id: UUID of the bill

    Returns: ok({bill: {...}, items: [...], totals: {...}}) or err
    """
    async with get_db() as db:
        bill = await db.get(Bill, uuid.UUID(bill_id))
        if not bill or bill.shop_id != SHOP_ID:
            return err("BILL_NOT_FOUND", f"Bill {bill_id} not found.")

        items_result = await db.execute(
            select(BillItem, Product)
            .join(Product, BillItem.product_id == Product.id)
            .where(BillItem.bill_id == uuid.UUID(bill_id))
        )
        rows = items_result.all()

        items_data = []
        gst_lines = []
        for item, product in rows:
            item.product = product  # attach for display_name
            items_data.append(_item_to_dict(item))
            if item.taxable_value:
                from app.tools.gst_utils import GSTLine
                gst_lines.append(
                    GSTLine(
                        qty=item.qty,
                        unit_price=item.unit_price,
                        gst_slab=item.gst_slab,
                        taxable_value=item.taxable_value,
                        cgst_amt=item.cgst_amt,
                        sgst_amt=item.sgst_amt,
                        line_total=item.line_total,
                    )
                )

        totals = compute_bill_totals(gst_lines) if gst_lines else None
        totals_dict = (
            {
                "subtotal": float(totals.subtotal),
                "cgst_total": float(totals.cgst_total),
                "sgst_total": float(totals.sgst_total),
                "round_off": float(totals.round_off),
                "grand_total": float(totals.grand_total),
            }
            if totals
            else None
        )

        return ok({
            "bill": _bill_to_dict(bill),
            "items": items_data,
            "preview_totals": totals_dict,
            "item_count": len(items_data),
        })


# ── Tool: finalize_bill ────────────────────────────────────────────────────────

async def finalize_bill(
    bill_id: str,
    payment_mode: str,
    idempotency_key: str,
    payment_ref: str = "",
) -> dict[str, Any]:
    """
    THE CRITICAL PATH. Finalizes a DRAFT bill atomically:

    1. Check idempotency_key — return cached result if already processed
    2. SELECT bill FOR UPDATE
    3. SELECT all bill_items, then SELECT each product FOR UPDATE
       (in product_id order to prevent deadlock)
    4. Hard-check qty_on_hand >= item.qty for every product
    5. Compute final GST totals
    6. Guard: grand_total >= aggregate cost (sell-below-cost check)
    7. Deduct stock + insert SALE movements
    8. Update bill to FINALIZED with all totals
    9. COMMIT

    Args:
        bill_id: UUID of the DRAFT bill
        payment_mode: CASH | UPI | CREDIT | CARD
        idempotency_key: Unique key from caller — prevents double-finalization on retry
        payment_ref: UPI transaction ID or card ref (optional)

    Returns: ok({bill: {...}}) or err with specific error_code
    """
    valid_modes = {"CASH", "UPI", "CREDIT", "CARD"}
    if payment_mode.upper() not in valid_modes:
        return err(
            "INVALID_PAYMENT_MODE",
            f"Payment mode must be one of: {', '.join(valid_modes)}",
        )

    async with get_db() as db:
        # ── Step 1: Idempotency check ────────────────────────────────────────
        existing_bill_result = await db.execute(
            select(Bill).where(Bill.idempotency_key == idempotency_key)
        )
        existing_bill = existing_bill_result.scalar_one_or_none()
        if existing_bill:
            items_result = await db.execute(
                select(BillItem, Product)
                .join(Product, BillItem.product_id == Product.id)
                .where(BillItem.bill_id == existing_bill.id)
            )
            rows = items_result.all()
            for item, product in rows:
                item.product = product
            return ok({
                "bill": _bill_to_dict(existing_bill, [r[0] for r in rows]),
                "message": "ℹ️ Bill already finalized (idempotency hit). Returning cached result.",
                "idempotent": True,
            })

        # ── Step 2: Lock bill ────────────────────────────────────────────────
        bill_result = await db.execute(
            select(Bill)
            .where(Bill.id == uuid.UUID(bill_id), Bill.shop_id == SHOP_ID)
            .with_for_update()
        )
        bill = bill_result.scalar_one_or_none()
        if not bill:
            return err("BILL_NOT_FOUND", f"Bill {bill_id} not found.")
        if bill.status != "DRAFT":
            return err(
                "BILL_NOT_DRAFT",
                f"Bill is already {bill.status}. Cannot finalize again.",
            )

        # ── Step 3: Load items, lock products in fixed order ─────────────────
        items_result = await db.execute(
            select(BillItem).where(BillItem.bill_id == uuid.UUID(bill_id))
        )
        items = items_result.scalars().all()
        if not items:
            return err("BILL_EMPTY", "Cannot finalize an empty bill. Add items first.")

        # Sort by product_id string to ensure consistent lock ordering
        items_sorted = sorted(items, key=lambda i: str(i.product_id))

        products: dict[uuid.UUID, Product] = {}
        for item in items_sorted:
            p_result = await db.execute(
                select(Product)
                .where(Product.id == item.product_id)
                .with_for_update()
            )
            p = p_result.scalar_one_or_none()
            if not p:
                return err(
                    "PRODUCT_NOT_FOUND",
                    f"Product {item.product_id} no longer exists.",
                )
            products[item.product_id] = p

        # ── Step 4: Stock sufficiency check ──────────────────────────────────
        for item in items_sorted:
            product = products[item.product_id]
            if product.qty_on_hand < item.qty:
                return err(
                    "INSUFFICIENT_STOCK",
                    f"Cannot finalize: only {float(product.qty_on_hand)} {product.unit} "
                    f"of '{product.display_name}' available, but {float(item.qty)} requested.",
                    product_id=str(product.id),
                    product_name=product.display_name,
                    available=float(product.qty_on_hand),
                    requested=float(item.qty),
                )

        # ── Step 5: Compute final GST ─────────────────────────────────────────
        gst_lines = []
        for item in items_sorted:
            product = products[item.product_id]
            gst_line = compute_gst_line(item.qty, product.sell_price, product.gst_slab)
            # Update stored GST values (prices might have changed since item was added)
            item.unit_price = product.sell_price
            item.gst_slab = product.gst_slab
            item.taxable_value = gst_line.taxable_value
            item.cgst_amt = gst_line.cgst_amt
            item.sgst_amt = gst_line.sgst_amt
            item.line_total = gst_line.line_total
            gst_lines.append(gst_line)

        totals = compute_bill_totals(gst_lines)

        # ── Step 6: Sell-below-cost guard ────────────────────────────────────
        aggregate_cost = sum(
            products[item.product_id].cost_price * item.qty
            for item in items_sorted
        )
        if totals.grand_total < aggregate_cost:
            return err(
                "SELL_BELOW_COST",
                f"Grand total ₹{float(totals.grand_total)} is below aggregate cost "
                f"₹{float(aggregate_cost):.2f}. Cannot finalize at a loss.",
                grand_total=float(totals.grand_total),
                aggregate_cost=float(aggregate_cost),
            )

        # ── Step 7: Deduct stock + insert movements ───────────────────────────
        for item in items_sorted:
            product = products[item.product_id]
            product.qty_on_hand -= item.qty
            db.add(
                StockMovement(
                    product_id=product.id,
                    type="SALE",
                    qty_delta=-item.qty,
                    ref_type="BILL",
                    ref_id=bill.id,
                    note=f"Sale on Bill #{str(bill.id)[:8]}",
                )
            )

        # ── Step 8: Finalize bill ─────────────────────────────────────────────
        bill.status = "FINALIZED"
        bill.payment_mode = payment_mode.upper()
        bill.payment_ref = payment_ref or None
        bill.subtotal = totals.subtotal
        bill.cgst_total = totals.cgst_total
        bill.sgst_total = totals.sgst_total
        bill.round_off = totals.round_off
        bill.grand_total = totals.grand_total
        bill.idempotency_key = idempotency_key
        bill.finalized_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.flush()

        # Attach products to items for response
        for item in items_sorted:
            item.product = products[item.product_id]

        return ok({
            "bill": _bill_to_dict(bill, items_sorted),
            "message": (
                f"✅ Bill #{str(bill.id)[:8]} finalized! "
                f"Grand total: ₹{float(totals.grand_total):.2f} | "
                f"Payment: {payment_mode.upper()}"
            ),
            "totals": {
                "subtotal": float(totals.subtotal),
                "cgst": float(totals.cgst_total),
                "sgst": float(totals.sgst_total),
                "round_off": float(totals.round_off),
                "grand_total": float(totals.grand_total),
            },
        })


# ── Tool: void_bill ────────────────────────────────────────────────────────────

async def void_bill(bill_id: str, reason: str) -> dict[str, Any]:
    """
    Void a FINALIZED bill. Reverses stock via VOID_REVERSAL movements.
    Does NOT delete the bill — it stays in the ledger marked VOID.

    Args:
        bill_id: UUID of the FINALIZED bill to void
        reason: Required explanation for the void

    Returns: ok({...}) or err
    """
    if not reason or not reason.strip():
        return err("REASON_REQUIRED", "A reason is required to void a bill.")

    async with get_db() as db:
        bill_result = await db.execute(
            select(Bill)
            .where(Bill.id == uuid.UUID(bill_id), Bill.shop_id == SHOP_ID)
            .with_for_update()
        )
        bill = bill_result.scalar_one_or_none()
        if not bill:
            return err("BILL_NOT_FOUND", f"Bill {bill_id} not found.")
        if bill.status == "VOID":
            return err("ALREADY_VOID", "Bill is already void.")
        if bill.status == "DRAFT":
            # Just delete the draft
            await db.delete(bill)
            return ok({"message": "✅ Draft bill deleted."})

        items_result = await db.execute(
            select(BillItem).where(BillItem.bill_id == uuid.UUID(bill_id))
        )
        items = items_result.scalars().all()

        # Reverse stock for each item
        for item in items:
            p_result = await db.execute(
                select(Product).where(Product.id == item.product_id).with_for_update()
            )
            product = p_result.scalar_one_or_none()
            if product:
                product.qty_on_hand += item.qty
                db.add(
                    StockMovement(
                        product_id=product.id,
                        type="VOID_REVERSAL",
                        qty_delta=item.qty,
                        ref_type="VOID",
                        ref_id=bill.id,
                        note=f"Void: {reason}",
                    )
                )

        bill.status = "VOID"
        await db.flush()

        return ok({
            "message": f"✅ Bill #{str(bill.id)[:8]} voided. Stock reversed. Reason: {reason}",
            "bill_id": str(bill.id),
        })


# ── Tool: list_bills ───────────────────────────────────────────────────────────

async def list_bills(
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    List bills, optionally filtered by status.

    Args:
        status: Filter by DRAFT | FINALIZED | VOID (optional)
        limit: Max bills to return (default 20)

    Returns: ok({bills: [...], count: N})
    """
    async with get_db() as db:
        query = select(Bill).where(Bill.shop_id == SHOP_ID).order_by(
            Bill.created_at.desc()
        ).limit(limit)
        if status:
            query = query.where(Bill.status == status.upper())
        result = await db.execute(query)
        bills = result.scalars().all()
        return ok({
            "bills": [_bill_to_dict(b) for b in bills],
            "count": len(bills),
        })
