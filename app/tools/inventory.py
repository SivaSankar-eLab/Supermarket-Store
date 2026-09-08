"""
KiranaBot — Inventory Tools

Tools exposed to the Claude Agent SDK for all stock-related operations.
Fuzzy product search uses Postgres pg_trgm for disambiguation without if/elif routing.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product, StockMovement, Shop
from app.tools import ok, err
from app.config import get_settings

settings = get_settings()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _product_to_dict(p: Product) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "brand": p.brand,
        "display_name": p.display_name,
        "unit": p.unit,
        "is_loose": p.is_loose,
        "hsn_code": p.hsn_code,
        "gst_slab": float(p.gst_slab),
        "cost_price": float(p.cost_price),
        "mrp": float(p.mrp) if p.mrp else None,
        "sell_price": float(p.sell_price),
        "qty_on_hand": float(p.qty_on_hand),
        "reorder_level": float(p.reorder_level),
        "low_stock": p.qty_on_hand <= p.reorder_level,
        "is_active": p.is_active,
    }


async def _get_shop_id(db: AsyncSession) -> uuid.UUID:
    shop_id = uuid.UUID(settings.shop_id)
    return shop_id


# ── Tool: find_product ─────────────────────────────────────────────────────────

async def find_product(query: str, limit: int = 5) -> dict[str, Any]:
    """
    Fuzzy-search products by name or brand using Postgres pg_trgm.
    Returns top candidates for disambiguation — never a single hard match.
    The agent asks the user to confirm if multiple results are returned.

    Args:
        query: Free-text product name/brand search
        limit: Max results to return (default 5)

    Returns: ok({candidates: [...]}) or err if no results
    """
    async with get_db() as db:
        shop_id = await _get_shop_id(db)

        # pg_trgm similarity search — falls back to ILIKE for short queries
        result = await db.execute(
            text("""
                SELECT id, name, brand, unit, is_loose, gst_slab,
                       cost_price, mrp, sell_price, qty_on_hand,
                       reorder_level, is_active, hsn_code,
                       similarity(name, :q) + similarity(COALESCE(brand,''), :q) AS score
                FROM products
                WHERE shop_id = :shop_id
                  AND is_active = true
                  AND (
                    similarity(name, :q) > 0.1
                    OR similarity(COALESCE(brand,''), :q) > 0.1
                    OR name ILIKE :like_q
                    OR COALESCE(brand,'') ILIKE :like_q
                  )
                ORDER BY score DESC
                LIMIT :limit
            """),
            {"q": query, "like_q": f"%{query}%", "shop_id": shop_id, "limit": limit},
        )
        rows = result.mappings().all()

        if not rows:
            return err(
                "PRODUCT_NOT_FOUND",
                f"No product found matching '{query}'. "
                "Try a different name or use add_product to create it.",
            )

        candidates = [
            {
                "id": str(r["id"]),
                "display_name": f"{r['brand']} {r['name']}".strip() if r["brand"] else r["name"],
                "unit": r["unit"],
                "sell_price": float(r["sell_price"]),
                "qty_on_hand": float(r["qty_on_hand"]),
                "gst_slab": float(r["gst_slab"]),
                "low_stock": r["qty_on_hand"] <= r["reorder_level"],
                "score": round(float(r["score"]), 3),
            }
            for r in rows
        ]

        # Auto-select ONLY if top candidate has high similarity score (>= 0.55)
        if candidates and candidates[0]["score"] >= 0.55:
            if len(candidates) == 1 or (candidates[0]["score"] - candidates[1]["score"] > 0.15):
                return ok({"candidates": candidates, "auto_selected": candidates[0]})

        return ok({"candidates": candidates, "auto_selected": None})


# ── Tool: get_stock ────────────────────────────────────────────────────────────

async def get_stock(product_id: str) -> dict[str, Any]:
    """
    Get current stock details for a specific product by ID.

    Args:
        product_id: UUID of the product

    Returns: ok({product: {...}}) or err if not found
    """
    async with get_db() as db:
        result = await db.execute(
            select(Product).where(
                Product.id == uuid.UUID(product_id),
                Product.shop_id == uuid.UUID(settings.shop_id),
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            return err("PRODUCT_NOT_FOUND", f"Product {product_id} not found.")
        return ok({"product": _product_to_dict(product)})


# ── Tool: list_low_stock ───────────────────────────────────────────────────────

async def list_low_stock() -> dict[str, Any]:
    """
    List all active products where qty_on_hand <= reorder_level.

    Returns: ok({products: [...], count: N})
    """
    async with get_db() as db:
        shop_id = uuid.UUID(settings.shop_id)
        result = await db.execute(
            select(Product).where(
                Product.shop_id == shop_id,
                Product.is_active == True,
                Product.qty_on_hand <= Product.reorder_level,
            ).order_by(Product.qty_on_hand)
        )
        products = result.scalars().all()
        return ok({
            "products": [_product_to_dict(p) for p in products],
            "count": len(products),
        })


# ── Tool: add_product ──────────────────────────────────────────────────────────

async def add_product(
    name: str,
    unit: str,
    gst_slab: float,
    cost_price: float,
    sell_price: float,
    brand: str = "",
    is_loose: bool = False,
    hsn_code: str = "",
    mrp: float | None = None,
    initial_qty: float = 0.0,
    reorder_level: float = 0.0,
    barcode: str = "",
) -> dict[str, Any]:
    """
    Add a new product to the catalog.

    Args:
        name: Product name (e.g., "Aashirvaad Atta")
        unit: Unit of measure — kg / g / l / ml / pkt / doz / pc
        gst_slab: GST rate — must be 0, 5, 12, 18, or 28
        cost_price: Purchase cost per unit (₹)
        sell_price: Selling price per unit (₹)
        brand: Brand name (optional)
        is_loose: True for loose items sold by weight/volume
        hsn_code: HSN code for GST compliance
        mrp: Maximum retail price (optional)
        initial_qty: Opening stock quantity
        reorder_level: Alert when stock falls to this level
        barcode: Barcode number (optional)

    Returns: ok({product: {...}}) or err on validation failure
    """
    valid_slabs = {0, 5, 12, 18, 28}
    if gst_slab not in valid_slabs:
        return err(
            "INVALID_GST_SLAB",
            f"GST slab must be one of {valid_slabs}. Got {gst_slab}.",
        )
    if sell_price < cost_price:
        return err(
            "SELL_BELOW_COST",
            f"Selling price ₹{sell_price} is below cost price ₹{cost_price}. "
            "Please confirm or adjust the price.",
        )
    valid_units = {"kg", "g", "l", "ml", "pkt", "doz", "pc", "box", "dozen", "pair"}
    if unit.lower() not in valid_units:
        return err(
            "INVALID_UNIT",
            f"Unit '{unit}' is not recognized. Valid units: {', '.join(sorted(valid_units))}",
        )

    async with get_db() as db:
        shop_id = uuid.UUID(settings.shop_id)
        clean_name = name.strip()
        clean_brand = brand.strip() if brand else None

        # Duplicate product check for this store
        stmt = select(Product).where(
            Product.shop_id == shop_id,
            Product.is_active == True,
            func.lower(Product.name) == clean_name.lower(),
        )
        if clean_brand:
            stmt = stmt.where(func.lower(Product.brand) == clean_brand.lower())
        else:
            stmt = stmt.where((Product.brand.is_(None)) | (Product.brand == ""))

        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return err(
                "DUPLICATE_PRODUCT",
                f"Product '{existing.display_name}' already exists in store catalog.",
            )

        product = Product(
            shop_id=shop_id,
            name=clean_name,
            brand=clean_brand,
            unit=unit.lower(),
            is_loose=is_loose,
            hsn_code=hsn_code.strip() if hsn_code else None,
            barcode=barcode.strip() if barcode else None,
            gst_slab=Decimal(str(gst_slab)),
            cost_price=Decimal(str(cost_price)),
            mrp=Decimal(str(mrp)) if mrp else None,
            sell_price=Decimal(str(sell_price)),
            qty_on_hand=Decimal(str(initial_qty)),
            reorder_level=Decimal(str(reorder_level)),
        )
        db.add(product)
        await db.flush()

        # Record opening stock movement if initial_qty > 0
        if initial_qty > 0:
            db.add(
                StockMovement(
                    product_id=product.id,
                    type="RECEIVE",
                    qty_delta=Decimal(str(initial_qty)),
                    ref_type="OPENING_STOCK",
                    note=f"Opening stock for {name}",
                )
            )

        await db.flush()
        return ok({"product": _product_to_dict(product), "message": f"✅ Added '{product.display_name}' to catalog."})


# ── Tool: receive_stock ────────────────────────────────────────────────────────

async def receive_stock(
    product_id: str,
    qty: float,
    cost_price: float,
    mrp: float | None = None,
    note: str = "",
) -> dict[str, Any]:
    """
    Record a stock receipt (purchase/delivery).
    Updates cost_price and optionally MRP. Logs a RECEIVE movement.

    Args:
        product_id: UUID of the product
        qty: Quantity received
        cost_price: New cost price per unit (₹)
        mrp: Updated MRP if changed (optional)
        note: Optional note about this receipt

    Returns: ok({product: {...}, movement: {...}}) or err
    """
    if qty <= 0:
        return err("INVALID_QTY", "Quantity must be greater than zero.")
    if cost_price <= 0:
        return err("INVALID_PRICE", "Cost price must be greater than zero.")

    async with get_db() as db:
        result = await db.execute(
            select(Product).where(
                Product.id == uuid.UUID(product_id),
                Product.shop_id == uuid.UUID(settings.shop_id),
            ).with_for_update()
        )
        product = result.scalar_one_or_none()
        if not product:
            return err("PRODUCT_NOT_FOUND", f"Product {product_id} not found.")

        product.cost_price = Decimal(str(cost_price))
        if mrp:
            product.mrp = Decimal(str(mrp))
        product.qty_on_hand += Decimal(str(qty))

        movement = StockMovement(
            product_id=product.id,
            type="RECEIVE",
            qty_delta=Decimal(str(qty)),
            ref_type="PURCHASE",
            note=note or f"Received {qty} {product.unit} of {product.display_name}",
        )
        db.add(movement)
        await db.flush()

        return ok({
            "message": f"✅ Received {qty} {product.unit} of {product.display_name}. "
                       f"New stock: {float(product.qty_on_hand)} {product.unit}",
            "product": _product_to_dict(product),
        })


# ── Tool: adjust_stock ─────────────────────────────────────────────────────────

async def adjust_stock(
    product_id: str,
    delta: float,
    reason: str,
) -> dict[str, Any]:
    """
    Manual stock adjustment (damage, theft, expiry, counting correction).
    delta can be positive (found more) or negative (written off).
    reason is REQUIRED and stored in the movement ledger.

    Args:
        product_id: UUID of the product
        delta: Qty change — positive to increase, negative to decrease
        reason: REQUIRED explanation (e.g., "Bag torn, 2kg damaged")

    Returns: ok({...}) or err
    """
    if not reason or not reason.strip():
        return err(
            "REASON_REQUIRED",
            "A reason is required for stock adjustments. "
            "Example: 'Damaged in transit' or 'Physical count correction'",
        )
    if delta == 0:
        return err("INVALID_DELTA", "Delta cannot be zero.")

    async with get_db() as db:
        result = await db.execute(
            select(Product).where(
                Product.id == uuid.UUID(product_id),
                Product.shop_id == uuid.UUID(settings.shop_id),
            ).with_for_update()
        )
        product = result.scalar_one_or_none()
        if not product:
            return err("PRODUCT_NOT_FOUND", f"Product {product_id} not found.")

        new_qty = product.qty_on_hand + Decimal(str(delta))
        if new_qty < 0:
            return err(
                "INSUFFICIENT_STOCK",
                f"Adjustment would result in negative stock. "
                f"Current: {float(product.qty_on_hand)}, Delta: {delta}.",
                available=float(product.qty_on_hand),
            )

        product.qty_on_hand = new_qty
        movement = StockMovement(
            product_id=product.id,
            type="ADJUST",
            qty_delta=Decimal(str(delta)),
            ref_type="MANUAL",
            note=reason,
        )
        db.add(movement)
        await db.flush()

        direction = "increased" if delta > 0 else "reduced"
        return ok({
            "message": f"✅ Stock {direction} by {abs(delta)} {product.unit}. "
                       f"New stock: {float(product.qty_on_hand)} {product.unit}. "
                       f"Reason logged: {reason}",
            "product": _product_to_dict(product),
        })


# ── Tool: list_products ────────────────────────────────────────────────────────

async def list_products(active_only: bool = True) -> dict[str, Any]:
    """
    List all products in the catalog.

    Args:
        active_only: If True, exclude discontinued products (default True)

    Returns: ok({products: [...], count: N})
    """
    async with get_db() as db:
        shop_id = uuid.UUID(settings.shop_id)
        query = select(Product).where(Product.shop_id == shop_id)
        if active_only:
            query = query.where(Product.is_active == True)
        query = query.order_by(Product.name)
        result = await db.execute(query)
        products = result.scalars().all()
        return ok({
            "products": [_product_to_dict(p) for p in products],
            "count": len(products),
        })


# ── Tool: update_product_price ─────────────────────────────────────────────────

async def update_product_price(
    product_id: str,
    sell_price: float | None = None,
    cost_price: float | None = None,
    mrp: float | None = None,
) -> dict[str, Any]:
    """
    Update pricing for a product.

    Args:
        product_id: UUID of the product
        sell_price: New selling price (optional)
        cost_price: New cost price (optional)
        mrp: New MRP (optional)

    Returns: ok({product: {...}}) or err
    """
    if not any([sell_price, cost_price, mrp]):
        return err("NO_CHANGES", "Provide at least one of sell_price, cost_price, or mrp.")

    async with get_db() as db:
        result = await db.execute(
            select(Product).where(
                Product.id == uuid.UUID(product_id),
                Product.shop_id == uuid.UUID(settings.shop_id),
            ).with_for_update()
        )
        product = result.scalar_one_or_none()
        if not product:
            return err("PRODUCT_NOT_FOUND", f"Product {product_id} not found.")

        effective_sell = Decimal(str(sell_price)) if sell_price else product.sell_price
        effective_cost = Decimal(str(cost_price)) if cost_price else product.cost_price

        if effective_sell < effective_cost:
            return err(
                "SELL_BELOW_COST",
                f"Selling price ₹{float(effective_sell)} is below cost ₹{float(effective_cost)}.",
            )

        if sell_price:
            product.sell_price = Decimal(str(sell_price))
        if cost_price:
            product.cost_price = Decimal(str(cost_price))
        if mrp:
            product.mrp = Decimal(str(mrp))

        await db.flush()
        return ok({
            "message": f"✅ Prices updated for {product.display_name}.",
            "product": _product_to_dict(product),
        })


# ── Tool: list_batches_fefo (First-Expired, First-Out Tracking) ────────────────

async def list_batches_fefo(product_id: str | None = None, days_threshold: int = 30) -> dict[str, Any]:
    """
    List inventory batches prioritized by Expiry Date (FEFO - First Expired, First Out)
    to prevent wastage and prioritize near-expiry products for sales and discounts.

    Args:
        product_id: Optional UUID of product to filter (default None for all items)
        days_threshold: Highlight batches expiring within N days (default 30)

    Returns: ok({fefo_queue: [...], near_expiry_count: int})
    """
    from datetime import date, timedelta
    today = date.today()
    threshold_date = today + timedelta(days=days_threshold)

    async with get_db() as db:
        # Get movements of type RECEIVE to track batch history and estimated shelf life
        query = select(StockMovement).join(Product, StockMovement.product_id == Product.id).where(
            Product.shop_id == uuid.UUID(settings.shop_id),
            StockMovement.type == "RECEIVE",
        )
        if product_id:
            query = query.where(StockMovement.product_id == uuid.UUID(product_id))

        query = query.order_by(StockMovement.created_at.asc())
        result = await db.execute(query)
        movements = result.scalars().all()

        batches = []
        for m in movements:
            received_dt = m.created_at.date() if hasattr(m.created_at, 'date') else today
            # Estimate default 90-day expiry from receive date for groceries if not specified
            est_expiry = received_dt + timedelta(days=90)
            days_to_expiry = (est_expiry - today).days

            is_expired = days_to_expiry < 0
            is_near_expiry = 0 <= days_to_expiry <= days_threshold

            batches.append({
                "batch_id": str(m.id)[:8].upper(),
                "product_id": str(m.product_id),
                "qty_received": float(m.qty_delta),
                "received_date": str(received_dt),
                "expiry_date": str(est_expiry),
                "days_remaining": days_to_expiry,
                "status": "EXPIRED" if is_expired else ("NEAR_EXPIRY" if is_near_expiry else "FRESH"),
                "fefo_priority": 1 if is_expired else (2 if is_near_expiry else 3),
            })

        batches.sort(key=lambda b: (b["fefo_priority"], b["days_remaining"]))

        return ok({
            "fefo_queue": batches,
            "total_batches": len(batches),
            "near_expiry_count": sum(1 for b in batches if b["status"] == "NEAR_EXPIRY"),
            "expired_count": sum(1 for b in batches if b["status"] == "EXPIRED"),
            "policy": "FEFO (First-Expired, First-Out) - Sell batches with earliest expiry dates first.",
        })

