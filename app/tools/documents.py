"""
KiranaBot — Document Generation Tools

PDF invoice: Jinja2 → WeasyPrint (branded HTML/CSS → PDF)
PPTX deck: matplotlib charts → python-pptx slides

Both are returned as file paths the Telegram bridge sends as documents.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from app.database import get_db
from app.models import Bill, BillItem, Product, Shop, Customer
from app.tools import ok, err
from app.tools.analytics import daily_close, sales_summary, gst_collected
from app.config import get_settings

settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)
DOCS_DIR = Path(settings.docs_output_dir)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_TEMPLATES = ROOT_DIR / "frontend" / "templates"
TEMPLATES_DIR = FRONTEND_TEMPLATES if FRONTEND_TEMPLATES.exists() else (ROOT_DIR / "templates")


def number_to_words_inr(amount: float | Decimal) -> str:
    """
    Convert a numeric amount in INR to formal Indian English words.
    e.g. 1450.50 -> "Indian Rupees One Thousand Four Hundred and Fifty and Fifty Paise Only"
    """
    try:
        amt = Decimal(str(amount)).quantize(Decimal("0.01"))
    except Exception:
        amt = Decimal("0.00")

    rupees = int(amt)
    paise = int((amt - Decimal(rupees)) * 100)

    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _under_thousand(n: int) -> str:
        res = []
        if n >= 100:
            res.append(f"{ones[n // 100]} Hundred")
            n %= 100
            if n > 0:
                res.append("and")
        if 0 < n < 20:
            res.append(ones[n])
        elif n >= 20:
            t = tens[n // 10]
            o = ones[n % 10]
            res.append(f"{t} {o}".strip())
        return " ".join(res).strip()

    if rupees == 0:
        words = "Zero Rupees"
    else:
        parts = []
        crores = rupees // 10000000
        rupees %= 10000000
        lakhs = rupees // 100000
        rupees %= 100000
        thousands = rupees // 1000
        rupees %= 1000
        rem = rupees

        if crores > 0:
            parts.append(f"{_under_thousand(crores)} Crore")
        if lakhs > 0:
            parts.append(f"{_under_thousand(lakhs)} Lakh")
        if thousands > 0:
            parts.append(f"{_under_thousand(thousands)} Thousand")
        if rem > 0:
            parts.append(_under_thousand(rem))
        words = f"Indian Rupees {' '.join(parts).strip()}"

    if paise > 0:
        paise_words = _under_thousand(paise)
        return f"{words} and {paise_words} Paise Only"
    return f"{words} Only"


def _create_minimalist_brand_logo(width: float = 80, height: float = 60):
    from reportlab.graphics.shapes import Drawing, Rect, PolyLine
    from reportlab.lib import colors

    d = Drawing(width, height)
    # Upper/Right bubble outline
    d.add(Rect(24, 20, 48, 36, rx=7, ry=7, strokeColor=colors.HexColor('#111827'), strokeWidth=2.4, fillColor=None))
    d.add(PolyLine([(64, 20), (70, 14), (60, 20)], strokeColor=colors.HexColor('#111827'), strokeWidth=2.4, fillColor=None))
    # Lower/Left bubble outline
    d.add(Rect(8, 6, 48, 36, rx=7, ry=7, strokeColor=colors.HexColor('#111827'), strokeWidth=2.4, fillColor=colors.white))
    d.add(PolyLine([(14, 6), (8, 0), (22, 6)], strokeColor=colors.HexColor('#111827'), strokeWidth=2.4, fillColor=colors.white))
    return d


def _render_invoice_reportlab(
    output_path: Path,
    shop: dict[str, Any],
    bill_id: str,
    bill_date: str,
    payment_mode: str,
    payment_ref: str,
    customer: dict[str, Any] | None,
    items: list[dict[str, Any]],
    gst_slabs: list[dict[str, Any]],
    subtotal: float,
    cgst_total: float,
    sgst_total: float,
    round_off: float,
    grand_total: float,
) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    # A4 Page = 595.27 x 841.89 pt. Printable width = 535 pt with 30 pt margins
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    styles = getSampleStyleSheet()

    style_top_meta = ParagraphStyle(
        "TopMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#6B7280"),
    )
    style_top_title = ParagraphStyle(
        "TopTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=32,
        textColor=colors.HexColor("#111827"),
    )
    style_label_bold = ParagraphStyle(
        "LabelBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#111827"),
    )
    style_th = ParagraphStyle(
        "TH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#111827"),
    )
    style_td = ParagraphStyle(
        "TD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#374151"),
    )
    style_td_bold = ParagraphStyle(
        "TDBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#111827"),
    )
    style_td_muted = ParagraphStyle(
        "TDMuted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#6B7280"),
    )

    elements = []

    # 1. Top Header: Number & Date + Large Invoice Title on Left, Logo on Right
    p_meta = Paragraph(f"Number: #{bill_id} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: {bill_date}", style_top_meta)
    p_title = Paragraph("Invoice", style_top_title)
    logo = _create_minimalist_brand_logo(80, 60)

    t_title_block = Table([[p_meta], [Spacer(1, 4)], [p_title]], colWidths=[445])
    t_title_block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    t_head = Table([[t_title_block, logo]], colWidths=[445, 90])
    t_head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_head)
    elements.append(Spacer(1, 16))

    # 2. Billed To & Billed From (2 Clean Columns)
    if customer:
        cust_name = customer.get("name", "Customer")
        cust_phone = customer.get("phone", "")
        cust_phone_str = f"<br/>{cust_phone}" if cust_phone else ""
        cust_bal = customer.get("current_balance")
        bal_str = f"<br/>Khata Balance: Rs. {float(cust_bal):,.2f}" if cust_bal is not None else ""
        cust_details = f"<b>{cust_name}</b>{cust_phone_str}<br/>Place of Supply: State Supply (07){bal_str}"
    else:
        cust_details = "<b>Walk-in Retail Customer</b><br/>Counter Sale / Cash<br/>Place of Supply: State Supply (07)"

    shop_name = shop.get("name", "Metro Supermarket")
    owner = shop.get("owner", "Store Manager")
    shop_addr = shop.get("address", "123 Main Street, Mumbai - 400001")
    gstin = shop.get("gstin", "27AABCU9603R1ZX")

    shop_details = f"<b>{shop_name}</b><br/>Proprietor: {owner}<br/>{shop_addr}<br/>GSTIN: {gstin}"

    t_to = Table([
        [Paragraph("<b>Billed to</b>", style_label_bold), Paragraph(f"<font size=8 color=#4B5563>{cust_details}</font>", styles["Normal"])]
    ], colWidths=[65, 195])
    t_to.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    t_from = Table([
        [Paragraph("<b>Billed from</b>", style_label_bold), Paragraph(f"<font size=8 color=#4B5563>{shop_details}</font>", styles["Normal"])]
    ], colWidths=[75, 200])
    t_from.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    t_meta_grid = Table([[t_to, t_from]], colWidths=[260, 275])
    t_meta_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_meta_grid)
    elements.append(Spacer(1, 20))

    # 3. Line Items Table (Airy, Minimalist, Clean)
    col_widths = [205, 50, 45, 55, 60, 45, 75]
    headers = ["Service Name", "HSN", "Amount", "Rate", "Taxable", "GST%", "Total"]
    item_rows = [[Paragraph(f"<b>{h}</b>", style_th) for h in headers]]

    for it in items:
        item_rows.append([
            Paragraph(f"<b>{it['name']}</b>", style_td_bold),
            Paragraph(str(it.get('hsn', '—')), style_td_muted),
            Paragraph(f"{it['qty']:g} {it['unit']}", style_td),
            Paragraph(f"Rs. {it['rate']:.2f}", style_td),
            Paragraph(f"Rs. {it['taxable']:.2f}", style_td),
            Paragraph(f"{it['gst_slab']:g}%", style_td),
            Paragraph(f"<b>Rs. {it['total']:.2f}</b>", style_td_bold),
        ])

    t_items = Table(item_rows, colWidths=col_widths, repeatRows=1)
    t_items.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor("#111827")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor("#111827")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#F3F4F6")),
        ("TOPPADDING", (0, 0), (-1, -1), 6.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 18))

    # 4. Financial Summary (Left Column: Words, Payment, GST mini table | Right Column: Totals with solid underline)
    amount_words = number_to_words_inr(grand_total)
    pay_ref_str = f" ({payment_ref})" if payment_ref else ""

    left_block = [
        [Paragraph("<b>Amount due</b>", style_label_bold)],
        [Paragraph(f"<font size=8 color=#4B5563>{amount_words}</font>", styles["Normal"])],
        [Spacer(1, 6)],
        [Paragraph("<b>Payment method</b>", style_label_bold)],
        [Paragraph(f"<font size=8 color=#4B5563>PAID · {payment_mode}{pay_ref_str}</font>", styles["Normal"])],
    ]

    if gst_slabs:
        gst_headers = ["GST Slab", "Taxable", "CGST", "SGST", "Total Tax"]
        gst_rows = [[Paragraph(f"<font size=7 color=#111827><b>{gh}</b></font>", styles["Normal"]) for gh in gst_headers]]
        for sl in gst_slabs:
            gst_rows.append([
                Paragraph(f"<font size=7 color=#374151>{sl['slab']:g}%</font>", styles["Normal"]),
                Paragraph(f"<font size=7 color=#374151>Rs. {sl['taxable']:.2f}</font>", styles["Normal"]),
                Paragraph(f"<font size=7 color=#374151>Rs. {sl['cgst']:.2f}</font>", styles["Normal"]),
                Paragraph(f"<font size=7 color=#374151>Rs. {sl['sgst']:.2f}</font>", styles["Normal"]),
                Paragraph(f"<font size=7 color=#111827>Rs. {sl['total']:.2f}</font>", styles["Normal"]),
            ])
        t_gst_mini = Table(gst_rows, colWidths=[45, 55, 45, 45, 55])
        t_gst_mini.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 0.75, colors.HexColor("#9CA3AF")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#9CA3AF")),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        left_block.extend([
            [Spacer(1, 6)],
            [t_gst_mini]
        ])

    t_left = Table(left_block, colWidths=[270])
    t_left.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    totals_rows = [
        [Paragraph("<font size=8.5 color=#4B5563>Subtotal</font>", styles["Normal"]), Paragraph(f"<font size=8.5 color=#111827>Rs. {subtotal:,.2f}</font>", styles["Normal"])],
        [Paragraph("<font size=8.5 color=#4B5563>Taxes (CGST)</font>", styles["Normal"]), Paragraph(f"<font size=8.5 color=#111827>Rs. {cgst_total:,.2f}</font>", styles["Normal"])],
        [Paragraph("<font size=8.5 color=#4B5563>Taxes (SGST)</font>", styles["Normal"]), Paragraph(f"<font size=8.5 color=#111827>Rs. {sgst_total:,.2f}</font>", styles["Normal"])],
    ]
    if round_off != 0:
        ro_prefix = "+" if round_off > 0 else ""
        totals_rows.append([
            Paragraph("<font size=8.5 color=#6B7280>Round Off Adjustment</font>", styles["Normal"]),
            Paragraph(f"<font size=8.5 color=#6B7280>{ro_prefix}Rs. {round_off:.2f}</font>", styles["Normal"])
        ])
    totals_rows.append([
        Paragraph("<font size=9.5 color=#111827><b>Total</b></font>", styles["Normal"]),
        Paragraph(f"<font size=10 color=#111827><b>Rs. {grand_total:,.2f}</b></font>", styles["Normal"])
    ])

    t_right_sum = Table(totals_rows, colWidths=[160, 95])
    t_right_sum.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, -1), (-1, -1), 2.5, colors.HexColor("#111827")),
    ]))

    t_summary = Table([[t_left, t_right_sum]], colWidths=[275, 260])
    t_summary.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 22))

    # 5. Bottom Grey Footer Banner
    terms_text = """<font size=8 color=#111827><b>Payment information & Terms</b></font><br/>
<font size=7 color=#4B5563>1. Goods once sold will not be returned without the original cash receipt.<br/>
2. All disputes are subject to local jurisdiction only. Computer-generated tax invoice.</font>"""
    site_text = f"""<font size=8 color=#111827><b>{shop.get('website', 'supermarketstore.in')}</b></font><br/>
<font size=7 color=#6B7280>{shop_addr.split(',')[0]} · {shop.get('phone', '+91 98765 43210')}<br/>
Powered by Supermarket ERP</font>"""

    p_terms = Paragraph(terms_text, styles["Normal"])
    p_site = Paragraph(site_text, styles["Normal"])

    t_banner = Table([[p_terms, p_site]], colWidths=[335, 180])
    t_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_banner)

    doc.build(elements)


# ── Tool: generate_invoice_pdf ─────────────────────────────────────────────────

async def generate_invoice_pdf(bill_id: str) -> dict[str, Any]:
    """
    Generate a branded GST invoice PDF for a FINALIZED bill.
    Uses WeasyPrint or ReportLab for HTML/PDF rendering.

    Args:
        bill_id: UUID of the FINALIZED bill

    Returns: ok({file_path: str, filename: str}) or err
    """
    from sqlalchemy import select

    async with get_db() as db:
        bill = await db.get(Bill, uuid.UUID(bill_id))
        if not bill or bill.shop_id != SHOP_ID:
            return err("BILL_NOT_FOUND", f"Bill {bill_id} not found.")
        if bill.status != "FINALIZED":
            return err(
                "BILL_NOT_FINALIZED",
                f"Only FINALIZED bills can generate invoices. Status: {bill.status}",
            )

        # Load items with products
        items_result = await db.execute(
            select(BillItem, Product)
            .join(Product, BillItem.product_id == Product.id)
            .where(BillItem.bill_id == uuid.UUID(bill_id))
            .order_by(Product.name)
        )
        rows = items_result.all()

        # Load customer & ledger balance
        customer = None
        cust_bal = 0.0
        if bill.customer_id:
            customer = await db.get(Customer, bill.customer_id)
            if customer:
                from app.tools.credit import _compute_balance
                cust_bal = float(await _compute_balance(db, customer.id))

        # Build GST slab summary
        slab_summary: dict[float, dict] = {}
        items_data = []
        for item, product in rows:
            slab = float(item.gst_slab)
            if slab not in slab_summary:
                slab_summary[slab] = {"taxable": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0")}
            slab_summary[slab]["taxable"] += item.taxable_value or Decimal("0")
            slab_summary[slab]["cgst"] += item.cgst_amt or Decimal("0")
            slab_summary[slab]["sgst"] += item.sgst_amt or Decimal("0")
            items_data.append({
                "name": product.display_name,
                "hsn": product.hsn_code or "N/A",
                "unit": product.unit,
                "qty": float(item.qty),
                "rate": float(item.unit_price),
                "taxable": float(item.taxable_value or 0),
                "gst_slab": slab,
                "cgst": float(item.cgst_amt or 0),
                "sgst": float(item.sgst_amt or 0),
                "total": float(item.line_total or 0),
            })

        gst_slabs = [
            {
                "slab": slab,
                "taxable": float(vals["taxable"]),
                "cgst": float(vals["cgst"]),
                "sgst": float(vals["sgst"]),
                "total": float(vals["cgst"] + vals["sgst"]),
            }
            for slab, vals in sorted(slab_summary.items())
            if vals["cgst"] > 0 or vals["sgst"] > 0
        ]

    # Load preferences for shop info
    from app.tools.preferences import load_preferences_for_context
    prefs = await load_preferences_for_context()

    shop_info = {
        "name": prefs.get("shop_name", settings.shop_name),
        "owner": prefs.get("owner_name", settings.shop_owner_name),
        "gstin": prefs.get("gstin", settings.shop_gstin) or "N/A",
        "address": prefs.get("address", settings.shop_address) or "",
        "footer": prefs.get("invoice_footer", "Thank you for shopping with us!"),
    }

    filename = f"invoice_{str(bill.id)[:8].upper()}.pdf"
    output_path = DOCS_DIR / filename

    cust_dict = None
    if customer:
        cust_dict = {
            "name": customer.name,
            "phone": customer.phone or "",
            "current_balance": cust_bal,
        }

    # Try HTML rendering via WeasyPrint first, fallback to ReportLab
    rendered = False
    try:
        from jinja2 import Environment, FileSystemLoader
        from weasyprint import HTML

        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template("invoice.html")
        html_content = template.render(
            bill_id=str(bill.id)[:8].upper(),
            bill_date=bill.finalized_at.strftime("%d %b %Y %H:%M") if bill.finalized_at else "",
            shop=shop_info,
            customer=cust_dict,
            items=items_data,
            gst_slabs=gst_slabs,
            subtotal=float(bill.subtotal or 0),
            cgst_total=float(bill.cgst_total or 0),
            sgst_total=float(bill.sgst_total or 0),
            round_off=float(bill.round_off or 0),
            grand_total=float(bill.grand_total or 0),
            amount_words=number_to_words_inr(float(bill.grand_total or 0)),
            payment_mode=bill.payment_mode or "CASH",
            payment_ref=bill.payment_ref or "",
        )
        HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
        rendered = True
    except Exception:
        rendered = False

    if not rendered:
        _render_invoice_reportlab(
            output_path=output_path,
            shop=shop_info,
            bill_id=str(bill.id)[:8].upper(),
            bill_date=bill.finalized_at.strftime("%d %b %Y %H:%M") if bill.finalized_at else "",
            payment_mode=bill.payment_mode or "CASH",
            payment_ref=bill.payment_ref or "",
            customer=cust_dict,
            items=items_data,
            gst_slabs=gst_slabs,
            subtotal=float(bill.subtotal or 0),
            cgst_total=float(bill.cgst_total or 0),
            sgst_total=float(bill.sgst_total or 0),
            round_off=float(bill.round_off or 0),
            grand_total=float(bill.grand_total or 0),
        )

    return ok({
        "file_path": str(output_path),
        "filename": filename,
        "message": f"✅ Invoice PDF generated: {filename}",
    })


# ── Tool: generate_analysis_deck ──────────────────────────────────────────────

async def generate_analysis_deck(period: str = "week") -> dict[str, Any]:
    """
    Generate a comprehensive, branded PPTX presentation analyzing store performance:
    - Slide 1: Executive Cover & Performance Overview
    - Slide 2: Sales & Revenue Key Metrics (KPI Cards)
    - Slide 3: Sales Velocity & Daily Revenue Trend (Real Bar Chart)
    - Slide 4: Top Performing Products (Real Horizontal Bar Chart & Breakdown)
    - Slide 5: Stock Health & Inventory Risk (Real Donut Chart & Low Stock Alerts)
    - Slide 6: GST Tax Breakdown & Compliance (Real Pie Chart & Tax Matrix)
    - Slide 7: Khata Receivables & Payment Channels

    Args:
        period: "today" | "week" | "month" | "year"

    Returns: ok({file_path: str, filename: str, message: str}) or err
    """
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from sqlalchemy import select, func, text

    # Fetch standard sales & GST analytics
    sales_data = await sales_summary(period)
    gst_data = await gst_collected(period, by_slab=True)

    if not sales_data["ok"]:
        return sales_data
    if not gst_data["ok"]:
        return gst_data

    s = sales_data["data"]
    g = gst_data["data"]
    start_date = s["start_date"]
    end_date = s["end_date"]
    d_start = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    d_end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    totals = s["totals"]

    # 1. Fetch Top Selling Products in period
    async with get_db() as db:
        top_items_res = await db.execute(
            text("""
                SELECT p.name, p.brand, p.unit,
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
            {"shop_id": SHOP_ID, "start": d_start, "end": d_end},
        )
        top_items = [
            {
                "name": f"{r.brand} {r.name}".strip() if r.brand else r.name,
                "qty": float(r.total_qty),
                "unit": r.unit,
                "revenue": float(r.total_revenue),
            }
            for r in top_items_res.all()
        ]

        # 2. Fetch Stock Health metrics
        total_skus_res = await db.execute(
            select(func.count(Product.id)).where(Product.shop_id == SHOP_ID, Product.is_active == True)
        )
        total_skus = total_skus_res.scalar() or 0

        low_stock_res = await db.execute(
            select(Product).where(
                Product.shop_id == SHOP_ID,
                Product.is_active == True,
                Product.qty_on_hand <= Product.reorder_level,
            ).order_by((Product.qty_on_hand - Product.reorder_level).asc())
        )
        low_stock_products = low_stock_res.scalars().all()
        low_stock_count = len(low_stock_products)
        out_of_stock_count = sum(1 for p in low_stock_products if p.qty_on_hand <= 0)
        healthy_stock_count = max(0, total_skus - low_stock_count)

        # 3. Fetch Payment mode breakdown in period
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
            {"shop_id": SHOP_ID, "start": d_start, "end": d_end},
        )
        payment_modes = [
            {"mode": r.payment_mode or "CASH", "count": r.count, "total": float(r.total)}
            for r in pay_res.all()
        ]

    # 4. Fetch Customer Credit Dues
    from app.tools.credit import list_customers_with_dues
    credit_data = await list_customers_with_dues()
    kd = credit_data.get("data", {"total_dues": 0.0, "count": 0, "customers": []}) if credit_data.get("ok") else {"total_dues": 0.0, "count": 0, "customers": []}

    # Load shop info
    from app.tools.preferences import load_preferences_for_context
    prefs = await load_preferences_for_context()
    shop_name = prefs.get("shop_name", settings.shop_name)

    # ── PPTX Initialization ───────────────────────────────────────────────────
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    # Brand Colors (Sleek Dark Theme)
    DARK_BG = RGBColor(0x0F, 0x17, 0x2A)       # Deep Navy Slate
    CARD_BG = RGBColor(0x1E, 0x29, 0x3B)       # Slate Card
    BORDER_COLOR = RGBColor(0x33, 0x41, 0x55)  # Muted Border
    ORANGE = RGBColor(0xFB, 0x92, 0x3C)        # Accent Coral
    TEAL = RGBColor(0x10, 0xB9, 0x81)          # Accent Emerald/Teal
    GOLD = RGBColor(0xFB, 0xBF, 0x24)          # Accent Gold
    RED = RGBColor(0xEF, 0x44, 0x44)           # Danger Red
    LIGHT = RGBColor(0xF8, 0xFA, 0xFC)         # Primary Text
    MUTED = RGBColor(0x94, 0xA3, 0xB8)         # Subtitle / Muted Text
    PURPLE = RGBColor(0x81, 0x8C, 0xF8)        # Accent Purple

    charts: list[str] = []

    def add_slide() -> Any:
        slide_layout = prs.slide_layouts[6]  # blank layout
        slide = prs.slides.add_slide(slide_layout)
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = DARK_BG
        return slide

    def add_card(slide: Any, left: float, top: float, width: float, height: float,
                 bg_color: RGBColor = CARD_BG, border_color: RGBColor = BORDER_COLOR) -> Any:
        shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height))
        shape.fill.solid()
        shape.fill.fore_color.rgb = bg_color
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1.5)
        return shape

    def add_header(slide: Any, title: str, subtitle: str = "") -> None:
        # Title text
        txBox = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.73), Inches(0.6))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(24)
        run.font.bold = True
        run.font.color.rgb = GOLD

        if subtitle:
            p2 = tf.add_paragraph()
            r2 = p2.add_run()
            r2.text = subtitle
            r2.font.size = Pt(12)
            r2.font.color.rgb = MUTED

    def add_text_box(slide: Any, text_val: str, left: float, top: float, width: float, height: float,
                     font_size: int = 14, bold: bool = False, color: RGBColor = LIGHT,
                     align: PP_ALIGN = PP_ALIGN.LEFT) -> Any:
        txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text_val
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = color
        return txBox

    def save_chart(fig: Any, name: str) -> str:
        path = str(DOCS_DIR / f"chart_{name}_{uuid.uuid4().hex[:6]}.png")
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="#0F172A", edgecolor="none")
        plt.close(fig)
        charts.append(path)
        return path

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 1: Executive Cover & Performance Overview
    # ═════════════════════════════════════════════════════════════════════════
    slide1 = add_slide()

    # Center Brand Card
    add_card(slide1, 1.0, 1.0, 11.33, 4.0, bg_color=CARD_BG, border_color=GOLD)
    add_text_box(slide1, shop_name.upper(), 1.5, 1.4, 10.33, 1.0, font_size=36, bold=True, color=GOLD, align=PP_ALIGN.CENTER)
    add_text_box(slide1, "STORE PERFORMANCE & BUSINESS INTELLIGENCE DECK", 1.5, 2.3, 10.33, 0.6, font_size=18, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
    add_text_box(slide1, f"Analysis Window: {start_date} to {end_date}  •  Period: {period.upper()}", 1.5, 3.0, 10.33, 0.5, font_size=14, color=LIGHT, align=PP_ALIGN.CENTER)
    add_text_box(slide1, f"Generated by Supermarket AI Assistant  •  {date.today().strftime('%d %B %Y')}", 1.5, 3.7, 10.33, 0.4, font_size=12, color=MUTED, align=PP_ALIGN.CENTER)

    # 4 Highlights Bottom Pills
    pills = [
        ("Total Sales", f"₹{totals['revenue']:,.2f}", ORANGE),
        ("Bills Finalized", f"{totals['bills']} Bills", TEAL),
        ("GST Collected", f"₹{totals['gst_collected']:,.2f}", GOLD),
        ("Low Stock Alerts", f"{low_stock_count} SKUs", RED if low_stock_count > 0 else TEAL),
    ]
    for idx, (label, val, col) in enumerate(pills):
        px = 1.0 + idx * 2.95
        add_card(slide1, px, 5.3, 2.5, 1.5, bg_color=CARD_BG, border_color=col)
        add_text_box(slide1, label, px + 0.1, 5.45, 2.3, 0.35, font_size=12, color=MUTED, align=PP_ALIGN.CENTER)
        add_text_box(slide1, val, px + 0.1, 5.85, 2.3, 0.6, font_size=20, bold=True, color=col, align=PP_ALIGN.CENTER)

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 2: Sales & Financial KPIs
    # ═════════════════════════════════════════════════════════════════════════
    slide2 = add_slide()
    add_header(slide2, "Sales & Financial Key Metrics", f"High-level financial and operational indicators for {period.title()}")

    kpi_cards = [
        ("Gross Revenue", f"₹{totals['revenue']:,.2f}", "Total settled bill sales", ORANGE),
        ("Invoices Finalized", f"{totals['bills']} Bills", "Customer transactions count", TEAL),
        ("Average Daily Run-rate", f"₹{totals['avg_daily_revenue']:,.2f}", "Daily sales velocity", GOLD),
        ("Average Bill Value", f"₹{totals['avg_bill_value']:,.2f}", "Average basket size per customer", LIGHT),
        ("GST Tax Collected", f"₹{totals['gst_collected']:,.2f}", "Total CGST + SGST collected", TEAL),
        ("Khata Outstanding Dues", f"₹{kd['total_dues']:,.2f}", f"{kd['count']} active customer balance", RED if kd["total_dues"] > 0 else TEAL),
    ]
    for i, (k_label, k_val, k_sub, k_col) in enumerate(kpi_cards):
        cx = 0.8 + (i % 3) * 4.0
        cy = 1.3 + (i // 3) * 2.7
        add_card(slide2, cx, cy, 3.7, 2.4, bg_color=CARD_BG, border_color=k_col)
        add_text_box(slide2, k_label, cx + 0.2, cy + 0.2, 3.3, 0.4, font_size=13, bold=True, color=MUTED)
        add_text_box(slide2, k_val, cx + 0.2, cy + 0.65, 3.3, 0.8, font_size=26, bold=True, color=k_col)
        add_text_box(slide2, k_sub, cx + 0.2, cy + 1.55, 3.3, 0.4, font_size=11, color=LIGHT)

    # Insight footer pill
    add_card(slide2, 0.8, 6.7, 11.73, 0.5, bg_color=CARD_BG, border_color=BORDER_COLOR)
    avg_str = f"💡 Sales insight: Generating an average of ₹{totals['avg_daily_revenue']:,.2f}/day with an average ticket size of ₹{totals['avg_bill_value']:,.2f}."
    add_text_box(slide2, avg_str, 1.0, 6.75, 11.33, 0.35, font_size=11, color=LIGHT)

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 3: Sales Velocity & Daily Revenue Trend (Real Bar Chart)
    # ═════════════════════════════════════════════════════════════════════════
    slide3 = add_slide()
    add_header(slide3, "Sales Velocity & Daily Revenue Trend", f"Daily progression of finalized sales from {start_date} to {end_date}")

    daily_data = s.get("daily_breakdown", [])
    if daily_data:
        fig_trend, ax_trend = plt.subplots(figsize=(8.0, 4.4))
        fig_trend.patch.set_facecolor("#0F172A")
        ax_trend.set_facecolor("#1E293B")

        days = [d["date"][-5:] for d in daily_data]
        revenues = [d["revenue"] for d in daily_data]

        bars = ax_trend.bar(days, revenues, color="#FB923C", edgecolor="#FDBA74", linewidth=1.2, width=0.55)
        ax_trend.set_xlabel("Date (MM-DD)", color="#F8FAFC", fontsize=10, labelpad=8)
        ax_trend.set_ylabel("Revenue (₹)", color="#F8FAFC", fontsize=10, labelpad=8)
        ax_trend.set_title(f"Daily Sales Volume (₹)", color="#FBBF24", fontsize=12, pad=12, fontweight="bold")
        ax_trend.tick_params(colors="#F8FAFC", labelsize=9)

        for spine in ax_trend.spines.values():
            spine.set_edgecolor("#334155")
        ax_trend.yaxis.grid(True, color="#334155", alpha=0.5, linestyle="--")

        # Value labels above bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax_trend.annotate(
                    f"₹{int(height):,}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    color="#F8FAFC", fontsize=8.5, fontweight="bold",
                )

        chart_trend_path = save_chart(fig_trend, "daily_trend")
        slide3.shapes.add_picture(chart_trend_path, Inches(0.8), Inches(1.3), Inches(8.0), Inches(5.2))

        # Stats Card on Right
        add_card(slide3, 9.1, 1.3, 3.4, 5.2, bg_color=CARD_BG, border_color=TEAL)
        add_text_box(slide3, "Trend Highlights", 9.3, 1.5, 3.0, 0.4, font_size=16, bold=True, color=GOLD)

        max_day = max(daily_data, key=lambda x: x["revenue"]) if daily_data else {"date": "N/A", "revenue": 0}
        min_day = min((d for d in daily_data if d["revenue"] > 0), key=lambda x: x["revenue"], default={"date": "N/A", "revenue": 0})

        trend_stats = [
            ("Peak Day", f"{max_day['date']}", f"₹{max_day['revenue']:,.2f}", ORANGE),
            ("Active Days", f"{len(daily_data)} Days tracked", f"₹{totals['revenue']:,.2f} Total", TEAL),
            ("Daily Run-rate", "Period Average", f"₹{totals['avg_daily_revenue']:,.2f}/day", GOLD),
            ("Average Ticket", f"{totals['bills']} total transactions", f"₹{totals['avg_bill_value']:,.2f}/bill", LIGHT),
        ]
        for idx, (label, sub, val, col) in enumerate(trend_stats):
            sy = 2.0 + idx * 1.15
            add_text_box(slide3, label, 9.3, sy, 3.0, 0.25, font_size=11, bold=True, color=MUTED)
            add_text_box(slide3, val, 9.3, sy + 0.22, 3.0, 0.4, font_size=16, bold=True, color=col)
            add_text_box(slide3, sub, 9.3, sy + 0.62, 3.0, 0.25, font_size=10, color=LIGHT)
    else:
        add_card(slide3, 1.5, 2.5, 10.33, 2.5, bg_color=CARD_BG, border_color=BORDER_COLOR)
        add_text_box(slide3, "No finalized sales recorded in this period.", 2.0, 3.5, 9.33, 0.8, font_size=18, color=MUTED, align=PP_ALIGN.CENTER)

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 4: Top Performing Products (Real Horizontal Bar Chart & Breakdown)
    # ═════════════════════════════════════════════════════════════════════════
    slide4 = add_slide()
    add_header(slide4, "Top Performing Products (Revenue & Volume)", "Best selling items ranked by total sales revenue")

    if top_items:
        fig_top, ax_top = plt.subplots(figsize=(6.5, 4.4))
        fig_top.patch.set_facecolor("#0F172A")
        ax_top.set_facecolor("#1E293B")

        # Reversed so highest is on top
        rev_items = list(reversed(top_items))
        names = [item["name"][:18] + ("…" if len(item["name"]) > 18 else "") for item in rev_items]
        revenues = [item["revenue"] for item in rev_items]

        bars_top = ax_top.barh(names, revenues, color="#10B981", edgecolor="#34D399", height=0.55)
        ax_top.set_xlabel("Revenue (₹)", color="#F8FAFC", fontsize=9, labelpad=8)
        ax_top.set_title("Top Products by Sales (₹)", color="#FBBF24", fontsize=12, pad=12, fontweight="bold")
        ax_top.tick_params(colors="#F8FAFC", labelsize=9)

        for spine in ax_top.spines.values():
            spine.set_edgecolor("#334155")
        ax_top.xaxis.grid(True, color="#334155", alpha=0.5, linestyle="--")

        for bar in bars_top:
            width = bar.get_width()
            ax_top.annotate(
                f" ₹{int(width):,}",
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(4, 0),
                textcoords="offset points",
                ha="left", va="center",
                color="#F8FAFC", fontsize=8.5, fontweight="bold",
            )

        chart_top_path = save_chart(fig_top, "top_products")
        slide4.shapes.add_picture(chart_top_path, Inches(0.8), Inches(1.3), Inches(6.5), Inches(5.2))

        # Products breakdown table card on Right
        add_card(slide4, 7.6, 1.3, 4.9, 5.2, bg_color=CARD_BG, border_color=TEAL)
        add_text_box(slide4, "Product Sales Breakdown", 7.8, 1.5, 4.5, 0.4, font_size=16, bold=True, color=GOLD)

        # Header
        add_text_box(slide4, "Product Name", 7.8, 2.0, 2.4, 0.3, font_size=10, bold=True, color=MUTED)
        add_text_box(slide4, "Qty Sold", 10.2, 2.0, 1.0, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
        add_text_box(slide4, "Revenue", 11.2, 2.0, 1.1, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)

        for idx, item in enumerate(top_items[:7]):
            iy = 2.35 + idx * 0.55
            add_text_box(slide4, f"{idx+1}. {item['name']}", 7.8, iy, 2.4, 0.3, font_size=11, bold=True, color=LIGHT)
            add_text_box(slide4, f"{item['qty']:g} {item['unit']}", 10.2, iy, 1.0, 0.3, font_size=11, color=TEAL, align=PP_ALIGN.RIGHT)
            add_text_box(slide4, f"₹{item['revenue']:,.2f}", 11.2, iy, 1.1, 0.3, font_size=11, bold=True, color=ORANGE, align=PP_ALIGN.RIGHT)
    else:
        add_card(slide4, 1.5, 2.5, 10.33, 2.5, bg_color=CARD_BG, border_color=BORDER_COLOR)
        add_text_box(slide4, "No individual product sales recorded in this period.", 2.0, 3.5, 9.33, 0.8, font_size=18, color=MUTED, align=PP_ALIGN.CENTER)

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 5: Stock Health & Inventory Risk (Real Donut Chart & Alerts)
    # ═════════════════════════════════════════════════════════════════════════
    slide5 = add_slide()
    add_header(slide5, "Stock Health & Inventory Status", "Catalog SKU health, out-of-stock risk assessment, and reorder alerts")

    # Donut chart of stock health
    stock_counts = [healthy_stock_count, max(0, low_stock_count - out_of_stock_count), out_of_stock_count]
    stock_labels = ["Healthy Stock", "Low Stock", "Out of Stock"]
    stock_colors = ["#10B981", "#FBBF24", "#EF4444"]

    fig_stock, ax_stock = plt.subplots(figsize=(5.4, 4.4))
    fig_stock.patch.set_facecolor("#0F172A")
    ax_stock.set_facecolor("#0F172A")

    valid_stock = [(c, l, col) for c, l, col in zip(stock_counts, stock_labels, stock_colors) if c > 0]
    if valid_stock:
        v_counts, v_labels, v_cols = zip(*valid_stock)
        wedges, texts, autotexts = ax_stock.pie(
            v_counts,
            labels=v_labels,
            autopct="%1.0f%%",
            pctdistance=0.75,
            colors=v_cols,
            textprops={"color": "#F8FAFC", "fontsize": 9.5},
            wedgeprops={"edgecolor": "#0F172A", "linewidth": 2.5, "width": 0.45},
        )
        for at in autotexts:
            at.set_fontsize(10)
            at.set_color("#0F172A")
            at.set_fontweight("bold")
        ax_stock.set_title(f"Total Catalog: {total_skus} Active SKUs", color="#FBBF24", fontsize=11, pad=10, fontweight="bold")
    else:
        ax_stock.text(0.5, 0.5, "No Catalog Data", ha="center", va="center", color="#F8FAFC")

    chart_stock_path = save_chart(fig_stock, "stock_health")
    slide5.shapes.add_picture(chart_stock_path, Inches(0.8), Inches(1.3), Inches(5.4), Inches(5.2))

    # Low Stock Items Table Card on Right
    add_card(slide5, 6.5, 1.3, 6.0, 5.2, bg_color=CARD_BG, border_color=RED if low_stock_count > 0 else TEAL)
    add_text_box(slide5, "Critical Stock Reorder Alerts", 6.7, 1.5, 5.6, 0.4, font_size=16, bold=True, color=GOLD)

    if low_stock_products:
        add_text_box(slide5, "Product (Brand & Name)", 6.7, 2.0, 3.2, 0.3, font_size=10, bold=True, color=MUTED)
        add_text_box(slide5, "On-Hand", 9.9, 2.0, 1.2, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
        add_text_box(slide5, "Reorder At", 11.1, 2.0, 1.2, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)

        for idx, prod in enumerate(low_stock_products[:7]):
            py = 2.35 + idx * 0.55
            p_name = f"{prod.brand} {prod.name}".strip() if prod.brand else prod.name
            is_out = prod.qty_on_hand <= 0
            badge_col = RED if is_out else ORANGE

            add_text_box(slide5, f"• {p_name[:24]}", 6.7, py, 3.2, 0.3, font_size=11, bold=True, color=LIGHT)
            add_text_box(slide5, f"{float(prod.qty_on_hand):g} {prod.unit}", 9.9, py, 1.2, 0.3, font_size=11, bold=True, color=badge_col, align=PP_ALIGN.RIGHT)
            add_text_box(slide5, f"{float(prod.reorder_level):g} {prod.unit}", 11.1, py, 1.2, 0.3, font_size=11, color=MUTED, align=PP_ALIGN.RIGHT)
    else:
        add_text_box(slide5, "✅ Excellent! All products are well above reorder levels.", 6.7, 3.0, 5.6, 0.8, font_size=14, bold=True, color=TEAL)
        add_text_box(slide5, f"All {total_skus} active SKUs are sufficiently stocked.", 6.7, 3.6, 5.6, 0.5, font_size=12, color=LIGHT)

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 6: GST Tax Breakdown & Compliance (Real Pie Chart & Tax Matrix)
    # ═════════════════════════════════════════════════════════════════════════
    slide6 = add_slide()
    add_header(slide6, "GST Collection & Tax Compliance", "Statutory GST breakdown across tax slabs (CGST + SGST)")

    slab_data = g.get("by_slab", [])
    gst_report = g.get("gst_report", {"total_taxable_value": 0, "total_cgst": 0, "total_sgst": 0, "total_gst_collected": 0})

    if slab_data:
        fig_gst, ax_gst = plt.subplots(figsize=(5.4, 4.4))
        fig_gst.patch.set_facecolor("#0F172A")
        ax_gst.set_facecolor("#0F172A")

        gst_labels = [f"{s['slab']}% Slab" for s in slab_data]
        gst_values = [s["total_gst"] for s in slab_data]
        gst_palette = ["#10B981", "#FBBF24", "#FB923C", "#818CF8", "#EC4899", "#38BDF8"]

        wedges, texts, autotexts = ax_gst.pie(
            gst_values,
            labels=gst_labels,
            autopct="%1.1f%%",
            pctdistance=0.75,
            colors=gst_palette[:len(gst_values)],
            textprops={"color": "#F8FAFC", "fontsize": 9.5},
            wedgeprops={"edgecolor": "#0F172A", "linewidth": 2.5, "width": 0.45},
        )
        for at in autotexts:
            at.set_fontsize(10)
            at.set_color("#0F172A")
            at.set_fontweight("bold")
        ax_gst.set_title(f"Total GST: ₹{gst_report['total_gst_collected']:,.2f}", color="#FBBF24", fontsize=11, pad=10, fontweight="bold")

        chart_gst_path = save_chart(fig_gst, "gst_slab")
        slide6.shapes.add_picture(chart_gst_path, Inches(0.8), Inches(1.3), Inches(5.4), Inches(5.2))

        # Tax Matrix Card on Right
        add_card(slide6, 6.5, 1.3, 6.0, 5.2, bg_color=CARD_BG, border_color=TEAL)
        add_text_box(slide6, "GST Slabs & Collections Summary", 6.7, 1.5, 5.6, 0.4, font_size=16, bold=True, color=GOLD)

        # 4 Mini Tax KPI boxes inside
        t_kpis = [
            ("Taxable Turnover", f"₹{gst_report['total_taxable_value']:,.2f}", LIGHT),
            ("Central GST (CGST)", f"₹{gst_report['total_cgst']:,.2f}", TEAL),
            ("State GST (SGST)", f"₹{gst_report['total_sgst']:,.2f}", TEAL),
            ("Total Tax Collected", f"₹{gst_report['total_gst_collected']:,.2f}", GOLD),
        ]
        for idx, (label, val, col) in enumerate(t_kpis):
            tx = 6.7 + (idx % 2) * 2.85
            ty = 2.0 + (idx // 2) * 1.15
            add_card(slide6, tx, ty, 2.7, 1.0, bg_color=DARK_BG, border_color=BORDER_COLOR)
            add_text_box(slide6, label, tx + 0.1, ty + 0.1, 2.5, 0.3, font_size=10, color=MUTED)
            add_text_box(slide6, val, tx + 0.1, ty + 0.4, 2.5, 0.5, font_size=14, bold=True, color=col)

        # Slabs Table Header
        add_text_box(slide6, "Slab", 6.7, 4.4, 1.0, 0.3, font_size=10, bold=True, color=MUTED)
        add_text_box(slide6, "Taxable (₹)", 7.8, 4.4, 1.5, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
        add_text_box(slide6, "CGST (₹)", 9.4, 4.4, 1.4, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
        add_text_box(slide6, "SGST (₹)", 10.9, 4.4, 1.4, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)

        for idx, sl in enumerate(slab_data[:3]):
            sy = 4.8 + idx * 0.45
            add_text_box(slide6, f"{sl['slab']}% GST", 6.7, sy, 1.0, 0.3, font_size=11, bold=True, color=LIGHT)
            add_text_box(slide6, f"₹{sl['taxable_value']:,.2f}", 7.8, sy, 1.5, 0.3, font_size=11, color=LIGHT, align=PP_ALIGN.RIGHT)
            add_text_box(slide6, f"₹{sl['cgst']:,.2f}", 9.4, sy, 1.4, 0.3, font_size=11, color=TEAL, align=PP_ALIGN.RIGHT)
            add_text_box(slide6, f"₹{sl['sgst']:,.2f}", 10.9, sy, 1.4, 0.3, font_size=11, color=TEAL, align=PP_ALIGN.RIGHT)
    else:
        add_card(slide6, 1.5, 2.5, 10.33, 2.5, bg_color=CARD_BG, border_color=BORDER_COLOR)
        add_text_box(slide6, "No taxable sales recorded in this period.", 2.0, 3.5, 9.33, 0.8, font_size=18, color=MUTED, align=PP_ALIGN.CENTER)

    # ═════════════════════════════════════════════════════════════════════════
    # SLIDE 7: Credit Ledger Receivables & Payment Channels
    # ═════════════════════════════════════════════════════════════════════════
    slide7 = add_slide()
    add_header(slide7, "Customer Credit Ledger & Payment Mix", "Customer credit receivables and transaction payment channels")

    # Left: Credit Overview & Payment Modes
    add_card(slide7, 0.8, 1.3, 5.5, 5.2, bg_color=CARD_BG, border_color=ORANGE if kd["total_dues"] > 0 else TEAL)
    add_text_box(slide7, "Credit Ledger Summary", 1.0, 1.5, 5.1, 0.4, font_size=16, bold=True, color=GOLD)

    add_card(slide7, 1.0, 2.0, 5.1, 1.2, bg_color=DARK_BG, border_color=BORDER_COLOR)
    add_text_box(slide7, "Total Outstanding Receivables", 1.2, 2.1, 4.7, 0.3, font_size=11, color=MUTED)
    add_text_box(slide7, f"₹{kd['total_dues']:,.2f}", 1.2, 2.45, 4.7, 0.6, font_size=24, bold=True, color=RED if kd["total_dues"] > 0 else TEAL)

    add_text_box(slide7, f"Active Accounts with Dues: {kd['count']} Customers", 1.0, 3.4, 5.1, 0.3, font_size=12, bold=True, color=LIGHT)

    # Payment mode pills
    add_text_box(slide7, "Payment Channels Mix", 1.0, 3.9, 5.1, 0.3, font_size=13, bold=True, color=GOLD)
    if payment_modes:
        for idx, pm in enumerate(payment_modes[:3]):
            pmy = 4.3 + idx * 0.65
            add_card(slide7, 1.0, pmy, 5.1, 0.55, bg_color=DARK_BG, border_color=BORDER_COLOR)
            add_text_box(slide7, f"• {pm['mode']}", 1.2, pmy + 0.1, 2.0, 0.35, font_size=11, bold=True, color=LIGHT)
            add_text_box(slide7, f"{pm['count']} bills", 3.2, pmy + 0.1, 1.0, 0.35, font_size=11, color=MUTED)
            add_text_box(slide7, f"₹{pm['total']:,.2f}", 4.2, pmy + 0.1, 1.7, 0.35, font_size=11, bold=True, color=TEAL, align=PP_ALIGN.RIGHT)
    else:
        add_text_box(slide7, "No payment records in period", 1.0, 4.5, 5.1, 0.4, font_size=11, color=MUTED)

    # Right: Top Debtors Table
    add_card(slide7, 6.6, 1.3, 5.9, 5.2, bg_color=CARD_BG, border_color=BORDER_COLOR)
    add_text_box(slide7, "Top Customer Balances (Receivables)", 6.8, 1.5, 5.5, 0.4, font_size=16, bold=True, color=GOLD)

    if kd.get("customers"):
        add_text_box(slide7, "Customer Name", 6.8, 2.0, 3.0, 0.3, font_size=10, bold=True, color=MUTED)
        add_text_box(slide7, "Phone", 9.8, 2.0, 1.4, 0.3, font_size=10, bold=True, color=MUTED)
        add_text_box(slide7, "Balance Due", 11.2, 2.0, 1.1, 0.3, font_size=10, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)

        for idx, cust in enumerate(kd["customers"][:7]):
            cy = 2.35 + idx * 0.55
            add_text_box(slide7, f"{idx+1}. {cust['name']}", 6.8, cy, 3.0, 0.3, font_size=11, bold=True, color=LIGHT)
            add_text_box(slide7, cust.get("phone", "—") or "—", 9.8, cy, 1.4, 0.3, font_size=11, color=MUTED)
            add_text_box(slide7, f"₹{cust['balance']:,.2f}", 11.2, cy, 1.1, 0.3, font_size=11, bold=True, color=RED, align=PP_ALIGN.RIGHT)
    else:
        add_text_box(slide7, "🎉 Zero outstanding customer credit! All accounts clear.", 6.8, 3.2, 5.5, 0.8, font_size=14, bold=True, color=TEAL)

    # ── Save PPTX Presentation ───────────────────────────────────────────────
    filename = f"analysis_{period}_{date.today().isoformat()}.pptx"
    output_path = DOCS_DIR / filename
    prs.save(str(output_path))

    # Clean up temporary chart images
    for chart_path in charts:
        try:
            os.remove(chart_path)
        except OSError:
            pass

    return ok({
        "file_path": str(output_path),
        "filename": filename,
        "message": f"✅ Presentation generated: {filename} ({len(prs.slides)} slides with real charts)",
    })
