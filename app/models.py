"""
KiranaBot — SQLAlchemy ORM Models

All models use UUID primary keys and TIMESTAMPTZ columns.
Business rules (constraints) are enforced both here and at the DB level.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


# ── Shop ──────────────────────────────────────────────────────────────────────

class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_name: Mapped[str] = mapped_column(Text, nullable=False)
    gstin: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=func.now()
    )

    products: Mapped[list["Product"]] = relationship(back_populates="shop")
    customers: Mapped[list["Customer"]] = relationship(back_populates="shop")
    bills: Mapped[list["Bill"]] = relationship(back_populates="shop")
    preferences: Mapped[list["Preference"]] = relationship(back_populates="shop")


# ── Product ───────────────────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("qty_on_hand >= 0", name="ck_qty_non_negative"),
        CheckConstraint("gst_slab IN (0, 5, 12, 18, 28)", name="ck_gst_slab_valid"),
        CheckConstraint("sell_price >= 0", name="ck_sell_price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(Text)
    barcode: Mapped[str | None] = mapped_column(Text, index=True)
    unit: Mapped[str] = mapped_column(Text, nullable=False)          # kg/g/l/ml/pkt/doz/pc
    is_loose: Mapped[bool] = mapped_column(Boolean, default=False)
    hsn_code: Mapped[str | None] = mapped_column(Text)
    gst_slab: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sell_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    qty_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=Decimal("0")
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=Decimal("0")
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=func.now(), onupdate=utcnow
    )

    shop: Mapped["Shop"] = relationship(back_populates="products")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="product"
    )
    bill_items: Mapped[list["BillItem"]] = relationship(back_populates="product")

    @property
    def display_name(self) -> str:
        if self.brand:
            return f"{self.brand} {self.name}"
        return self.name


# ── StockMovement (immutable ledger) ─────────────────────────────────────────

class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "type IN ('RECEIVE','SALE','ADJUST','VOID_REVERSAL')",
            name="ck_movement_type_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(Text)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="stock_movements")


# ── Customer ──────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("shop_id", "phone", name="uq_customer_phone_per_shop"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())

    shop: Mapped["Shop"] = relationship(back_populates="customers")
    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="customer"
    )
    bills: Mapped[list["Bill"]] = relationship(back_populates="customer")


# ── Bill ──────────────────────────────────────────────────────────────────────

class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','FINALIZED','VOID')", name="ck_bill_status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    payment_mode: Mapped[str | None] = mapped_column(Text)
    payment_ref: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cgst_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sgst_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    round_off: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    grand_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    finalized_at: Mapped[datetime | None] = mapped_column()

    shop: Mapped["Shop"] = relationship(back_populates="bills")
    customer: Mapped["Customer | None"] = relationship(back_populates="bills")
    items: Mapped[list["BillItem"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan"
    )


# ── BillItem ──────────────────────────────────────────────────────────────────

class BillItem(Base):
    __tablename__ = "bill_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_bill_item_qty_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    gst_slab: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    taxable_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cgst_amt: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sgst_amt: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    bill: Mapped["Bill"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="bill_items")


# ── CreditTransaction (append-only ledger) ────────────────────────────────────

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        CheckConstraint("type IN ('CREDIT','PAYMENT')", name="ck_credit_type_valid"),
        CheckConstraint("amount > 0", name="ck_credit_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)   # CREDIT|PAYMENT
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    mode: Mapped[str | None] = mapped_column(Text)
    ref_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="credit_transactions")


# ── Preference ────────────────────────────────────────────────────────────────

class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (
        UniqueConstraint("shop_id", "key", name="uq_pref_shop_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=func.now(), onupdate=utcnow
    )

    shop: Mapped["Shop"] = relationship(back_populates="preferences")


# ── ProcessedTelegramUpdate (dedup at ingestion) ──────────────────────────────

class ProcessedTelegramUpdate(Base):
    __tablename__ = "processed_telegram_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=func.now()
    )
