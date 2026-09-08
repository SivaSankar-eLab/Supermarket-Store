"""
KiranaBot — Interactive Shop Operations Dashboard
Provides real-time business metrics, interactive charts, inventory health,
invoices table with PDF download, customer khata ledger statements,
multimodal AI vision & barcode scanning, and PPTX deck export.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, text, desc

from app.config import get_settings
from app.database import get_db
from app.models import Bill, BillItem, Product, Shop, Customer, CreditTransaction
from app.tools.analytics import sales_summary, gst_collected, daily_close
from app.tools.credit import list_customers_with_dues
from app.tools.documents import generate_analysis_deck, generate_invoice_pdf
from app.tools.preferences import load_preferences_for_context
from app.tools.vision import identify_product_from_image, lookup_by_barcode
from app.tools.inventory import add_product


settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)
router = APIRouter(tags=["dashboard"])

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_TEMPLATES_DIR = ROOT_DIR / "frontend" / "templates"
templates = Jinja2Templates(directory=str(FRONTEND_TEMPLATES_DIR))


# ── REST API: Dashboard Stats ──────────────────────────────────────────────────

@router.get("/api/dashboard/stats")
async def get_dashboard_stats(period: str = Query("week", pattern="^(today|week|month|year)$")) -> dict[str, Any]:
    """Return consolidated analytics for the chosen period."""
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
        start_date = today - timedelta(days=6)

    # 1. Sales & GST summaries
    sales_res = await sales_summary(period)
    gst_res = await gst_collected(period, by_slab=True)

    sales_data = sales_res.get("data", {}) if sales_res.get("ok") else {}
    gst_data = gst_res.get("data", {}) if gst_res.get("ok") else {}

    # 2. Database direct queries for Top items, Stock health, Payments
    async with get_db() as db:
        # Top 7 Products in period
        top_res = await db.execute(
            text("""
                SELECT p.id, p.name, p.brand, p.unit,
                       COALESCE(SUM(bi.qty), 0) as total_qty,
                       COALESCE(SUM(bi.line_total), 0) as total_revenue
                FROM bill_items bi
                JOIN bills b ON bi.bill_id = b.id
                JOIN products p ON bi.product_id = p.id
                WHERE b.shop_id = :shop_id
                  AND b.status = 'FINALIZED'
                  AND DATE(b.finalized_at) >= :start
                  AND DATE(b.finalized_at) <= :end
                GROUP BY p.id, p.name, p.brand, p.unit
                ORDER BY total_revenue DESC
                LIMIT 7
            """),
            {"shop_id": SHOP_ID, "start": start_date, "end": today},
        )
        top_products = [
            {
                "id": str(r.id),
                "name": f"{r.brand} {r.name}".strip() if r.brand else r.name,
                "qty": float(r.total_qty),
                "unit": r.unit,
                "revenue": float(r.total_revenue),
            }
            for r in top_res.all()
        ]

        # Stock Health summary
        total_skus_res = await db.execute(
            select(
                func.count(Product.id).label("total"),
                func.coalesce(func.sum(Product.qty_on_hand * Product.cost_price), 0).label("stock_val"),
            ).where(Product.shop_id == SHOP_ID, Product.is_active == True)
        )
        t_row = total_skus_res.one()
        total_skus = t_row.total
        total_stock_value = float(t_row.stock_val)

        low_stock_res = await db.execute(
            select(Product).where(
                Product.shop_id == SHOP_ID,
                Product.is_active == True,
                Product.qty_on_hand <= Product.reorder_level,
            ).order_by((Product.qty_on_hand - Product.reorder_level).asc())
        )
        low_stock_items = low_stock_res.scalars().all()
        low_stock_count = len(low_stock_items)
        out_of_stock_count = sum(1 for p in low_stock_items if p.qty_on_hand <= 0)
        healthy_stock_count = max(0, total_skus - low_stock_count)

        # Payment mode breakdown
        pay_res = await db.execute(
            text("""
                SELECT payment_mode, COUNT(id) as count, COALESCE(SUM(grand_total), 0) as total
                FROM bills
                WHERE shop_id = :shop_id
                  AND status = 'FINALIZED'
                  AND DATE(finalized_at) >= :start
                  AND DATE(finalized_at) <= :end
                GROUP BY payment_mode
                ORDER BY total DESC
            """),
            {"shop_id": SHOP_ID, "start": start_date, "end": today},
        )
        payments = [
            {"mode": r.payment_mode or "CASH", "count": r.count, "total": float(r.total)}
            for r in pay_res.all()
        ]

    # 3. Credit ledger summary
    credit_res = await list_customers_with_dues()
    credit_data = credit_res.get("data", {"total_dues": 0.0, "count": 0, "customers": []}) if credit_res.get("ok") else {}

    # 4. Preferences & Shop info
    prefs = await load_preferences_for_context()

    return {
        "ok": True,
        "period": period,
        "start_date": str(start_date),
        "end_date": str(today),
        "shop": {
            "name": prefs.get("shop_name", settings.shop_name),
            "owner": prefs.get("owner_name", settings.shop_owner_name),
            "gstin": prefs.get("gstin", settings.shop_gstin) or "—",
            "ai_provider": prefs.get("ai_provider", "gemini"),
        },
        "sales": sales_data.get("totals", {
            "bills": 0, "revenue": 0.0, "gst_collected": 0.0, "avg_daily_revenue": 0.0, "avg_bill_value": 0.0
        }),
        "daily_breakdown": sales_data.get("daily_breakdown", []),
        "top_products": top_products,
        "payment_breakdown": payments,
        "stock_health": {
            "total_skus": total_skus,
            "healthy_count": healthy_stock_count,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "total_stock_value": total_stock_value,
            "critical_items": [
                {
                    "name": f"{p.brand} {p.name}".strip() if p.brand else p.name,
                    "unit": p.unit,
                    "qty_on_hand": float(p.qty_on_hand),
                    "reorder_level": float(p.reorder_level),
                    "sell_price": float(p.sell_price),
                    "is_out": p.qty_on_hand <= 0,
                }
                for p in low_stock_items[:8]
            ],
        },
        "gst": {
            "report": gst_data.get("gst_report", {
                "total_taxable_value": 0.0, "total_cgst": 0.0, "total_sgst": 0.0, "total_gst_collected": 0.0, "bills_count": 0
            }),
            "slabs": gst_data.get("by_slab", []),
        },
        "credit": credit_data,
        "khata": credit_data,
    }


# ── REST API: Inventory List ──────────────────────────────────────────────────

@router.get("/api/dashboard/inventory")
async def get_dashboard_inventory(
    search: str = Query("", description="Search term for product or brand"),
    low_stock_only: bool = Query(False, description="Filter only low stock items"),
    slab: str = Query("ALL", description="Filter by GST slab"),
) -> dict[str, Any]:
    """Return all catalog products with current stock status and metadata."""
    async with get_db() as db:
        query = select(Product).where(Product.shop_id == SHOP_ID, Product.is_active == True)
        if search.strip():
            term = f"%{search.strip()}%"
            query = query.where((Product.name.ilike(term)) | (Product.brand.ilike(term)))
        if low_stock_only:
            query = query.where(Product.qty_on_hand <= Product.reorder_level)
        if slab != "ALL":
            try:
                s_val = float(slab)
                query = query.where(Product.gst_slab == Decimal(str(s_val)))
            except ValueError:
                pass

        query = query.order_by(Product.name.asc())
        res = await db.execute(query)
        products = res.scalars().all()

        return {
            "ok": True,
            "count": len(products),
            "products": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "brand": p.brand or "",
                    "display_name": p.display_name,
                    "unit": p.unit,
                    "is_loose": p.is_loose,
                    "hsn_code": p.hsn_code or "—",
                    "gst_slab": float(p.gst_slab),
                    "cost_price": float(p.cost_price),
                    "mrp": float(p.mrp) if p.mrp else None,
                    "sell_price": float(p.sell_price),
                    "qty_on_hand": float(p.qty_on_hand),
                    "reorder_level": float(p.reorder_level),
                    "is_low_stock": p.qty_on_hand <= p.reorder_level,
                    "is_out_of_stock": p.qty_on_hand <= 0,
                }
                for p in products
            ],
        }


# ── REST API: Recent Bills / Invoices ─────────────────────────────────────────

@router.get("/api/dashboard/bills")
async def get_dashboard_bills(limit: int = Query(40, ge=1, le=100)) -> dict[str, Any]:
    """Return recent finalized bills with customer info and line item count."""
    async with get_db() as db:
        res = await db.execute(
            select(Bill, Customer.name.label("customer_name"), func.count(BillItem.id).label("items_count"))
            .outerjoin(Customer, Bill.customer_id == Customer.id)
            .outerjoin(BillItem, Bill.id == BillItem.bill_id)
            .where(Bill.shop_id == SHOP_ID, Bill.status == "FINALIZED")
            .group_by(Bill.id, Customer.name)
            .order_by(desc(Bill.finalized_at))
            .limit(limit)
        )
        rows = res.all()

        return {
            "ok": True,
            "count": len(rows),
            "bills": [
                {
                    "id": str(bill.id),
                    "short_id": str(bill.id)[:8].upper(),
                    "finalized_at": bill.finalized_at.strftime("%d %b %Y, %I:%M %p") if bill.finalized_at else "—",
                    "customer_name": cust_name or "Walk-in Customer",
                    "payment_mode": bill.payment_mode or "CASH",
                    "payment_ref": bill.payment_ref or "—",
                    "items_count": items_count,
                    "subtotal": float(bill.subtotal or 0),
                    "cgst_total": float(bill.cgst_total or 0),
                    "sgst_total": float(bill.sgst_total or 0),
                    "total_gst": float((bill.cgst_total or 0) + (bill.sgst_total or 0)),
                    "round_off": float(bill.round_off or 0),
                    "grand_total": float(bill.grand_total or 0),
                }
                for bill, cust_name, items_count in rows
            ],
        }


# ── REST API: Customer Credit Statement ───────────────────────────────────────

@router.get("/api/dashboard/credit/statement/{customer_id}")
@router.get("/api/dashboard/khata/statement/{customer_id}")
async def get_customer_statement(customer_id: str) -> dict[str, Any]:
    """Return full transaction ledger history for a specific customer."""
    try:
        c_uuid = uuid.UUID(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Customer UUID")

    async with get_db() as db:
        customer = await db.get(Customer, c_uuid)
        if not customer or customer.shop_id != SHOP_ID:
            raise HTTPException(status_code=404, detail="Customer not found")

        from sqlalchemy import case

        bal_res = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (CreditTransaction.type == "CREDIT", CreditTransaction.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ) - func.coalesce(
                    func.sum(
                        case(
                            (CreditTransaction.type == "PAYMENT", CreditTransaction.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                )
            ).where(CreditTransaction.customer_id == c_uuid)
        )
        current_balance = float(bal_res.scalar() or 0)

        tx_res = await db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.customer_id == c_uuid)
            .order_by(CreditTransaction.created_at.desc())
        )
        txs = tx_res.scalars().all()

        return {
            "ok": True,
            "customer": {
                "id": str(customer.id),
                "name": customer.name,
                "phone": customer.phone or "—",
                "current_balance": current_balance,
            },
            "transactions": [
                {
                    "id": str(t.id),
                    "type": t.type,
                    "amount": float(t.amount),
                    "mode": t.mode or "—",
                    "note": t.note or "",
                    "ref_bill_id": str(t.ref_bill_id)[:8].upper() if t.ref_bill_id else None,
                    "created_at": t.created_at.strftime("%d %b %Y, %I:%M %p"),
                }
                for t in txs
            ],
        }


# ── REST API: Export PPTX & Download Invoice ───────────────────────────────────

@router.get("/api/dashboard/export-deck")
async def export_presentation_deck(period: str = Query("week", pattern="^(today|week|month|year)$")):
    """Generate and return PPTX analysis deck as downloadable attachment."""
    deck_res = await generate_analysis_deck(period)
    if not deck_res.get("ok"):
        err_msg = deck_res.get("message") or "Deck generation failed"
        raise HTTPException(status_code=500, detail=err_msg)

    file_path = deck_res["data"]["file_path"]
    filename = deck_res["data"]["filename"]
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )


@router.get("/api/dashboard/download-invoice/{bill_id}")
async def download_invoice(bill_id: str):
    """Generate and return PDF invoice for a finalized bill."""
    pdf_res = await generate_invoice_pdf(bill_id)
    if not pdf_res.get("ok"):
        err_msg = pdf_res.get("message") or "Invoice generation failed"
        raise HTTPException(status_code=400, detail=err_msg)

    file_path = pdf_res["data"]["file_path"]
    filename = pdf_res["data"]["filename"]
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )


# ── REST API: Vision & Barcode Scanning ────────────────────────────────────────

@router.post("/api/dashboard/scan-product")
async def scan_product_endpoint(
    file: UploadFile | None = File(None),
    barcode: str | None = Form(None),
) -> dict[str, Any]:
    """
    Identify a product via uploaded packaging photo or exact barcode number.
    """
    if barcode and barcode.strip():
        res = await lookup_by_barcode(barcode=barcode.strip())
        return res

    if not file:
        raise HTTPException(status_code=400, detail="Either an image file or barcode number is required.")

    scan_dir = Path("docs_output/scans")
    scan_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    temp_path = scan_dir / f"web_scan_{uuid.uuid4().hex[:8]}{ext}"

    contents = await file.read()
    with open(temp_path, "wb") as f:
        f.write(contents)

    res = await identify_product_from_image(image_path=str(temp_path.resolve()))
    return res


@router.post("/api/dashboard/add-product")
async def add_product_from_dashboard(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """
    Register a newly identified product into the store catalog.
    """
    name = str(payload.get("name", "")).strip()
    unit = str(payload.get("unit", "pkt")).strip().lower()
    gst_slab = float(payload.get("gst_slab", 5))
    cost_price = float(payload.get("cost_price", 0))
    sell_price = float(payload.get("sell_price", 0))
    brand = str(payload.get("brand", "")).strip()
    mrp = float(payload.get("mrp")) if payload.get("mrp") else None
    barcode = str(payload.get("barcode", "")).strip()
    initial_qty = float(payload.get("initial_qty", 0))
    reorder_level = float(payload.get("reorder_level", 0))

    if not name or sell_price <= 0:
        raise HTTPException(status_code=400, detail="Name and valid selling price are required.")

    res = await add_product(
        name=name,
        unit=unit,
        gst_slab=gst_slab,
        cost_price=cost_price,
        sell_price=sell_price,
        brand=brand,
        mrp=mrp,
        barcode=barcode,
        initial_qty=initial_qty,
        reorder_level=reorder_level,
    )
    return res


# ── HTML Single Page Application Dashboard ────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request) -> HTMLResponse:
    """Serve modern, interactive store operations dashboard."""
    prefs = await load_preferences_for_context()
    shop_name = prefs.get("shop_name", settings.shop_name)
    ai_provider = prefs.get("ai_provider", "gemini")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "shop_name": shop_name,
            "ai_provider": ai_provider,
        },
    )
