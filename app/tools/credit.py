"""
Supermarket Operations — Customer Credit Ledger Tools

Credit Ledger is an event-sourced ledger:
  balance = SUM(CREDIT) - SUM(PAYMENT)   ← computed, never stored as a mutable column.

This makes it impossible to corrupt the balance — you can always reconstruct it
from the full transaction history.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Customer, CreditTransaction
from app.tools import ok, err
from app.config import get_settings

settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _customer_to_dict(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "phone": c.phone,
    }


def _txn_to_dict(t: CreditTransaction) -> dict:
    return {
        "id": str(t.id),
        "type": t.type,
        "amount": float(t.amount),
        "mode": t.mode,
        "ref_bill_id": str(t.ref_bill_id) if t.ref_bill_id else None,
        "note": t.note,
        "created_at": t.created_at.isoformat(),
    }


async def _compute_balance(db: AsyncSession, customer_id: uuid.UUID) -> Decimal:
    """Compute balance as SUM(CREDIT) - SUM(PAYMENT) from the ledger."""
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (CreditTransaction.type == "CREDIT", CreditTransaction.amount),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("total_credit"),
            func.coalesce(
                func.sum(
                    case(
                        (CreditTransaction.type == "PAYMENT", CreditTransaction.amount),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("total_payment"),
        ).where(CreditTransaction.customer_id == customer_id)
    )
    row = result.one()
    return row.total_credit - row.total_payment


# ── Tool: add_customer ─────────────────────────────────────────────────────────

async def add_customer(name: str, phone: str = "") -> dict[str, Any]:
    """
    Add a new customer to the credit ledger.

    Args:
        name: Customer name
        phone: Phone number (optional but recommended for uniqueness)

    Returns: ok({customer: {...}}) or err if phone already registered
    """
    async with get_db() as db:
        if phone:
            existing = await db.execute(
                select(Customer).where(
                    Customer.shop_id == SHOP_ID,
                    Customer.phone == phone,
                )
            )
            if existing.scalar_one_or_none():
                return err(
                    "DUPLICATE_PHONE",
                    f"A customer with phone {phone} already exists.",
                )

        customer = Customer(
            shop_id=SHOP_ID,
            name=name.strip(),
            phone=phone.strip() if phone else None,
        )
        db.add(customer)
        await db.flush()
        return ok({
            "customer": _customer_to_dict(customer),
            "message": f"✅ Customer '{name}' added to credit accounts.",
        })


# ── Tool: find_customer ────────────────────────────────────────────────────────

async def find_customer(query: str) -> dict[str, Any]:
    """
    Search for a customer by name or phone number.

    Args:
        query: Name or phone number fragment

    Returns: ok({customers: [...]}) or err
    """
    async with get_db() as db:
        result = await db.execute(
            select(Customer).where(
                Customer.shop_id == SHOP_ID,
                (Customer.name.ilike(f"%{query}%")) | (Customer.phone.ilike(f"%{query}%")),
            ).order_by(Customer.name)
        )
        customers = result.scalars().all()
        if not customers:
            return err(
                "CUSTOMER_NOT_FOUND",
                f"No customer found matching '{query}'. "
                "Use add_customer to create a new one.",
            )
        return ok({"customers": [_customer_to_dict(c) for c in customers]})


# ── Tool: get_customer_balance ─────────────────────────────────────────────────

async def get_customer_balance(customer_id: str) -> dict[str, Any]:
    """
    Get the current credit balance for a customer.
    Balance = total credit given - total payments received.
    A positive balance means the customer OWES money.

    Args:
        customer_id: UUID of the customer

    Returns: ok({customer: {...}, balance: float, transactions: [...]}) or err
    """
    async with get_db() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or customer.shop_id != SHOP_ID:
            return err("CUSTOMER_NOT_FOUND", f"Customer {customer_id} not found.")

        balance = await _compute_balance(db, customer.id)

        txns_result = await db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.customer_id == customer.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(10)
        )
        txns = txns_result.scalars().all()

        return ok({
            "customer": _customer_to_dict(customer),
            "balance": float(balance),
            "balance_label": (
                f"₹{float(balance):.2f} outstanding (customer owes you)"
                if balance > 0
                else f"₹{abs(float(balance)):.2f} advance (you owe customer)"
                if balance < 0
                else "No outstanding balance"
            ),
            "recent_transactions": [_txn_to_dict(t) for t in txns],
        })


# ── Tool: add_credit ──────────────────────────────────────────────────────────

async def add_credit(
    customer_id: str,
    amount: float,
    ref_bill_id: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """
    Record goods/services given on credit (customer owes).
    Typically called automatically when finalizing a bill with CREDIT payment mode.

    Args:
        customer_id: UUID of the customer
        amount: Amount credited (₹) — must be > 0
        ref_bill_id: Associated bill ID (optional)
        note: Description (optional)

    Returns: ok({balance: float, transaction: {...}})
    """
    if amount <= 0:
        return err("INVALID_AMOUNT", "Credit amount must be greater than zero.")

    async with get_db() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or customer.shop_id != SHOP_ID:
            return err("CUSTOMER_NOT_FOUND", f"Customer {customer_id} not found.")

        txn = CreditTransaction(
            customer_id=customer.id,
            type="CREDIT",
            amount=Decimal(str(amount)),
            ref_bill_id=uuid.UUID(ref_bill_id) if ref_bill_id else None,
            note=note or f"Credit of Rs. {amount:.2f}",
        )
        db.add(txn)
        await db.flush()

        balance = await _compute_balance(db, customer.id)
        return ok({
            "message": f"✅ ₹{amount:.2f} credited to {customer.name}. "
                       f"Outstanding balance: ₹{float(balance):.2f}",
            "balance": float(balance),
            "transaction": _txn_to_dict(txn),
        })


# ── Tool: record_payment ───────────────────────────────────────────────────────

async def record_payment(
    customer_id: str,
    amount: float,
    mode: str = "CASH",
    note: str = "",
) -> dict[str, Any]:
    """
    Record a payment received from a customer against their credit balance.

    Args:
        customer_id: UUID of the customer
        amount: Payment amount (₹) — must be > 0
        mode: Payment mode — CASH | UPI | CARD (default CASH)
        note: Optional note

    Returns: ok({balance: float, transaction: {...}}) or err
    """
    if amount <= 0:
        return err("INVALID_AMOUNT", "Payment amount must be greater than zero.")

    valid_modes = {"CASH", "UPI", "CARD"}
    mode = mode.upper()
    if mode not in valid_modes:
        return err("INVALID_MODE", f"Payment mode must be one of: {', '.join(valid_modes)}")

    async with get_db() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or customer.shop_id != SHOP_ID:
            return err("CUSTOMER_NOT_FOUND", f"Customer {customer_id} not found.")

        current_balance = await _compute_balance(db, customer.id)
        if Decimal(str(amount)) > current_balance:
            # Allow overpayment but warn
            warning = (
                f"⚠️ Payment ₹{amount:.2f} exceeds outstanding balance "
                f"₹{float(current_balance):.2f}. Recording as advance."
            )
        else:
            warning = None

        txn = CreditTransaction(
            customer_id=customer.id,
            type="PAYMENT",
            amount=Decimal(str(amount)),
            mode=mode,
            note=note or f"Payment via {mode}",
        )
        db.add(txn)
        await db.flush()

        new_balance = await _compute_balance(db, customer.id)
        result = {
            "message": f"✅ Received ₹{amount:.2f} from {customer.name} via {mode}. "
                       f"Remaining balance: ₹{float(new_balance):.2f}",
            "balance": float(new_balance),
            "transaction": _txn_to_dict(txn),
        }
        if warning:
            result["warning"] = warning
        return ok(result)


# ── Tool: list_customers_with_dues ─────────────────────────────────────────────

async def list_customers_with_dues() -> dict[str, Any]:
    """
    List all customers who have an outstanding balance (positive credit balance).

    Returns: ok({customers: [{...customer, balance: float}], total_dues: float})
    """
    async with get_db() as db:
        customers_result = await db.execute(
            select(Customer).where(Customer.shop_id == SHOP_ID).order_by(Customer.name)
        )
        all_customers = customers_result.scalars().all()

        dues = []
        total = Decimal("0")
        for customer in all_customers:
            balance = await _compute_balance(db, customer.id)
            if balance > 0:
                dues.append({
                    **_customer_to_dict(customer),
                    "balance": float(balance),
                })
                total += balance

        dues.sort(key=lambda x: x["balance"], reverse=True)
        return ok({
            "customers": dues,
            "count": len(dues),
            "total_dues": float(total),
            "message": (
                f"📋 {len(dues)} customers owe a total of ₹{float(total):.2f}"
                if dues
                else "✅ No outstanding dues! All accounts are settled."
            ),
        })


# ── Tool: get_customer_statement ───────────────────────────────────────────────

async def get_customer_statement(
    customer_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Get the full transaction history (statement) for a customer.

    Args:
        customer_id: UUID of the customer
        limit: Max transactions to return (default 50)

    Returns: ok({customer: {...}, balance: float, transactions: [...]})
    """
    async with get_db() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or customer.shop_id != SHOP_ID:
            return err("CUSTOMER_NOT_FOUND", f"Customer {customer_id} not found.")

        txns_result = await db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.customer_id == customer.id)
            .order_by(CreditTransaction.created_at.asc())
            .limit(limit)
        )
        txns = txns_result.scalars().all()
        balance = await _compute_balance(db, customer.id)

        return ok({
            "customer": _customer_to_dict(customer),
            "balance": float(balance),
            "transactions": [_txn_to_dict(t) for t in txns],
            "transaction_count": len(txns),
        })


# ── Tool: create_payment_reminder ──────────────────────────────────────────────

async def create_payment_reminder(
    customer_id: str,
    language: str = "english",
    upi_vpa: str | None = None,
) -> dict[str, Any]:
    """
    Generate a polite payment reminder message for WhatsApp/SMS/Telegram
    including outstanding balance, due breakdown, and UPI direct payment link.

    Args:
        customer_id: UUID of the customer
        language: "english" | "hindi" | "tamil" (default "english")
        upi_vpa: Shop UPI ID for direct payment link (optional)

    Returns: ok({customer: {...}, balance: float, reminder_text: str, upi_link: str})
    """
    async with get_db() as db:
        customer = await db.get(Customer, uuid.UUID(customer_id))
        if not customer or customer.shop_id != SHOP_ID:
            return err("CUSTOMER_NOT_FOUND", f"Customer {customer_id} not found.")

        balance = await _compute_balance(db, customer.id)
        if balance <= 0:
            return ok({
                "customer": _customer_to_dict(customer),
                "balance": float(balance),
                "message": f"Customer {customer.name} has no outstanding balance (₹0.00).",
                "reminder_needed": False,
            })

        shop_name = settings.shop_name
        vpa = upi_vpa or "shop@upi"
        upi_link = f"upi://pay?pa={vpa}&pn={shop_name.replace(' ', '%20')}&am={float(balance):.2f}&cu=INR"

        text = (
            f"Dear {customer.name},\n\n"
            f"This is a gentle reminder from {shop_name}. Your total outstanding balance is ₹{float(balance):.2f}.\n\n"
            f"Kindly clear the dues at your earliest convenience via the UPI link below or at our counter:\n"
            f"💳 UPI Link: {upi_link}\n\n"
            f"Thank you,\n{shop_name}"
        )

        return ok({
            "customer": _customer_to_dict(customer),
            "balance": float(balance),
            "language": language,
            "upi_link": upi_link,
            "reminder_text": text,
            "reminder_needed": True,
        })
