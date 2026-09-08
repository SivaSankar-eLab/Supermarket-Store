"""Initial schema — KiranaBot

Revision ID: 001
Revises: 
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── shops ─────────────────────────────────────────────────────────────────
    op.create_table(
        "shops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("owner_name", sa.Text, nullable=False),
        sa.Column("gstin", sa.Text),
        sa.Column("address", sa.Text),
        sa.Column("chat_id", sa.BigInteger, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
    )

    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("brand", sa.Text),
        sa.Column("unit", sa.Text, nullable=False),          # kg/g/l/ml/pkt/doz/pc
        sa.Column("is_loose", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("hsn_code", sa.Text),
        sa.Column("gst_slab", sa.Numeric(5, 2), nullable=False),  # 0/5/12/18/28
        sa.Column("cost_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("mrp", sa.Numeric(10, 2)),
        sa.Column("sell_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("qty_on_hand", sa.Numeric(10, 3), nullable=False,
                  server_default="0"),
        sa.Column("reorder_level", sa.Numeric(10, 3), server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint("qty_on_hand >= 0", name="ck_qty_non_negative"),
        sa.CheckConstraint("gst_slab IN (0, 5, 12, 18, 28)", name="ck_gst_slab_valid"),
        sa.CheckConstraint("sell_price >= 0", name="ck_sell_price_non_negative"),
    )
    # GIN trigram index for fuzzy name search
    op.execute(
        "CREATE INDEX idx_products_name_trgm ON products "
        "USING GIN (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_products_brand_trgm ON products "
        "USING GIN (brand gin_trgm_ops)"
    )

    # ── stock_movements ───────────────────────────────────────────────────────
    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=False),
        sa.Column("type", sa.Text, nullable=False),   # RECEIVE|SALE|ADJUST|VOID_REVERSAL
        sa.Column("qty_delta", sa.Numeric(10, 3), nullable=False),
        sa.Column("ref_type", sa.Text),               # BILL|MANUAL|VOID
        sa.Column("ref_id", postgresql.UUID(as_uuid=True)),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint("type IN ('RECEIVE','SALE','ADJUST','VOID_REVERSAL')",
                           name="ck_movement_type_valid"),
    )

    # ── customers ─────────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("phone", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("shop_id", "phone", name="uq_customer_phone_per_shop"),
    )

    # ── bills ─────────────────────────────────────────────────────────────────
    op.create_table(
        "bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id")),
        sa.Column("status", sa.Text, nullable=False, server_default="'DRAFT'"),
        sa.Column("payment_mode", sa.Text),              # CASH|UPI|CREDIT|CARD
        sa.Column("payment_ref", sa.Text),
        sa.Column("subtotal", sa.Numeric(10, 2)),
        sa.Column("cgst_total", sa.Numeric(10, 2)),
        sa.Column("sgst_total", sa.Numeric(10, 2)),
        sa.Column("round_off", sa.Numeric(5, 2)),
        sa.Column("grand_total", sa.Numeric(10, 2)),
        sa.Column("idempotency_key", sa.Text, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.Column("finalized_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("status IN ('DRAFT','FINALIZED','VOID')",
                           name="ck_bill_status_valid"),
    )

    # ── bill_items ────────────────────────────────────────────────────────────
    op.create_table(
        "bill_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("gst_slab", sa.Numeric(5, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(10, 2)),
        sa.Column("cgst_amt", sa.Numeric(10, 2)),
        sa.Column("sgst_amt", sa.Numeric(10, 2)),
        sa.Column("line_total", sa.Numeric(10, 2)),
        sa.CheckConstraint("qty > 0", name="ck_bill_item_qty_positive"),
    )

    # ── credit_transactions ───────────────────────────────────────────────────
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text, nullable=False),          # CREDIT|PAYMENT
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("mode", sa.Text),                          # CASH|UPI
        sa.Column("ref_bill_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bills.id")),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint("type IN ('CREDIT','PAYMENT')",
                           name="ck_credit_type_valid"),
        sa.CheckConstraint("amount > 0", name="ck_credit_amount_positive"),
    )

    # ── preferences ───────────────────────────────────────────────────────────
    op.create_table(
        "preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("shop_id", "key", name="uq_pref_shop_key"),
    )

    # ── processed_telegram_updates (idempotency at ingestion) ─────────────────
    op.create_table(
        "processed_telegram_updates",
        sa.Column("update_id", sa.BigInteger, primary_key=True),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("processed_telegram_updates")
    op.drop_table("preferences")
    op.drop_table("credit_transactions")
    op.drop_table("bill_items")
    op.drop_table("bills")
    op.drop_table("customers")
    op.drop_table("stock_movements")
    op.drop_table("products")
    op.drop_table("shops")
