"""
KiranaBot — Vision & Barcode Recognition Tools

Identifies products, barcodes, packaging labels, and price tags from images
using multimodal AI vision models (Gemini / Claude). Cross-references matches
against the PostgreSQL catalog.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Product, Shop
from app.tools import ok, err
from app.tools.inventory import _product_to_dict, find_product

settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)
logger = logging.getLogger(__name__)


VISION_PROMPT = """You are an expert product identifier and barcode scanner for an Indian supermarket/kirana store.
Examine this image carefully (it could be grocery packaging, raw staples like sugar/salt/atta/rice/dal/oil, a barcode/QR label, price tag, or invoice).

Key Commodity Identification Rules:
- White crystals in a bowl/bag/box = Sugar (or Salt if labeled salt). NEVER confuse sugar with atta or flour.
- Fine wheat flour in a bag/packet = Atta (or Maida/Besan).
- Grains in bags/jars = Rice / Wheat / Toor Dal / Moong Dal.
- Golden/yellow liquid in pouches/bottles = Cooking Oil / Ghee.
- Packaged snacks/biscuits/soaps = Read exact brand name and product name printed on the packet.

Extract the following details and return ONLY a valid JSON object (no markdown, no backticks):
{
  "is_product": true,
  "brand": "Brand name (e.g., Madhur, Dhampure, Tata, Aashirvaad, Fortune, Amul, Parle, Surf Excel, Maggi, Britannia, Dabur, or '' if unbranded/loose)",
  "name": "Product item name (e.g., Sugar, Atta, Salt, Toor Dal, Basmati Rice, Refined Sunflower Oil, Marie Gold Biscuits)",
  "net_qty": 1.0,
  "unit": "kg" (choose strictly from: kg, g, l, ml, pkt, pc, doz, box),
  "barcode": "Exact barcode numbers if readable, or null",
  "mrp": 50.0 (Printed MRP if readable, or null),
  "category": "Sugar & Sweeteners | Grains & Flours | Edible Oils | Dairy | Spices | Biscuits & Snacks | Personal Care | Household Cleaners | Beverages",
  "suggested_gst_slab": 5 (must be one of: 0, 5, 12, 18, 28; staple unbranded sugar/salt/grains is 0 or 5),
  "hsn_code": "Estimated HSN code or null",
  "confidence": 0.95,
  "summary": "Short concise summary of what was identified"
}
If the image is not a recognizable grocery product, staple item, price tag, or barcode, set "is_product": false and explain in "summary".
"""


# ── Vision Engine Provider Callers ─────────────────────────────────────────────

async def _analyze_image_gemini(image_path: Path) -> dict[str, Any]:
    """Call Google Gemini Vision with image bytes."""
    import google.generativeai as genai
    from PIL import Image

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash" if "2.5" in settings.gemini_model else settings.gemini_model)

    img = Image.open(image_path)
    response = model.generate_content([VISION_PROMPT, img])
    raw_text = response.text.strip()

    # Clean code blocks if present
    cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

    return json.loads(cleaned)


async def _analyze_image_claude(image_path: Path) -> dict[str, Any]:
    """Call Anthropic Claude 3.5 Sonnet Vision with image base64."""
    from anthropic import AsyncAnthropic

    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("sk-ant-dummy"):
        raise RuntimeError("Valid ANTHROPIC_API_KEY is not set.")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    mime_type, _ = mimetypes.guess_type(str(image_path))
    mime_type = mime_type or "image/jpeg"

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    raw_text = message.content[0].text.strip()
    cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    return json.loads(cleaned)


# ── Tool: identify_product_from_image ──────────────────────────────────────────

async def identify_product_from_image(image_path: str, context: str = "") -> dict[str, Any]:
    """
    Identify a grocery product or barcode from a photo.
    Extracts brand, name, net weight, barcode, MRP, and suggested GST slab.
    Cross-references against the store's PostgreSQL catalog.

    Args:
        image_path: Absolute or relative file path to the image
        context: Optional user hint (e.g., 'received 50 packets', 'add to Ravi bill')

    Returns: ok({status: 'MATCHED_IN_CATALOG' | 'NEW_PRODUCT_SUGGESTION', ...}) or err
    """
    path = Path(image_path)
    if not path.exists():
        return err("FILE_NOT_FOUND", f"Image file not found at {image_path}")

    # 1. Run Multimodal Vision with available provider
    detected: dict[str, Any] = {}
    try:
        if settings.gemini_api_key and not settings.gemini_api_key.startswith("sk-"):
            try:
                detected = await _analyze_image_gemini(path)
            except Exception as gemini_err:
                if settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-dummy"):
                    logger.info("Falling back to Claude vision: %s", gemini_err)
                    detected = await _analyze_image_claude(path)
                else:
                    raise
        elif settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-dummy"):
            detected = await _analyze_image_claude(path)
        else:
            detected = await _analyze_image_gemini(path)
    except Exception as exc:
        logger.exception("Vision analysis error: %s", exc)
        return err("VISION_ERROR", f"Failed to analyze product image: {str(exc)}")

    if not detected.get("is_product", True):
        return err("UNRECOGNIZED_PRODUCT", detected.get("summary", "Could not identify a grocery item in image."))

    brand = (detected.get("brand") or "").strip()
    name = (detected.get("name") or "").strip()
    barcode = detected.get("barcode")
    unit = (detected.get("unit") or "pkt").lower()
    mrp = detected.get("mrp")
    suggested_gst = detected.get("suggested_gst_slab", 5)

    # 2. Database Lookup: Try Barcode match first
    matched_product = None
    async with get_db() as db:
        if barcode:
            b_res = await db.execute(
                select(Product).where(
                    Product.shop_id == SHOP_ID,
                    Product.is_active == True,
                    Product.barcode == str(barcode).strip(),
                )
            )
            matched_product = b_res.scalar_one_or_none()

    # 3. Database Lookup: Fuzzy and Keyword Match on Catalog
    if not matched_product and (brand or name):
        clean_brand = brand if brand.lower() not in {"generic", "unbranded", "loose", "none"} else ""
        clean_name = name

        search_queries = []
        if clean_brand and clean_name:
            search_queries.append(f"{clean_brand} {clean_name}")
        if clean_name:
            search_queries.append(clean_name)
        if clean_brand:
            search_queries.append(clean_brand)

        for query in search_queries:
            search_res = await find_product(query=query, limit=5)
            if search_res.get("ok"):
                candidates = search_res["data"].get("candidates", [])
                auto_sel = search_res["data"].get("auto_selected")

                candidate_to_check = auto_sel or (candidates[0] if candidates and candidates[0].get("score", 0) >= 0.35 else None)
                if candidate_to_check:
                    cand_display = candidate_to_check["display_name"].lower()
                    # Verify commodity keyword match (e.g. 'sugar' in 'Local Sugar', 'atta' in 'Aashirvaad Atta')
                    name_words = [w.lower() for w in clean_name.split() if len(w) > 2]
                    keyword_match = any(w in cand_display for w in name_words) or (candidate_to_check.get("score", 0) >= 0.6)

                    if keyword_match:
                        async with get_db() as db:
                            p_res = await db.execute(
                                select(Product).where(Product.id == uuid.UUID(candidate_to_check["id"]))
                            )
                            matched_product = p_res.scalar_one_or_none()
                            if matched_product:
                                break

    # 4. Result formatting
    if matched_product:
        p_dict = _product_to_dict(matched_product)
        return ok({
            "status": "MATCHED_IN_CATALOG",
            "detected": detected,
            "product": p_dict,
            "message": (
                f"🎯 Matched in Catalog: **{matched_product.display_name}**\n"
                f"• Stock On-Hand: {float(matched_product.qty_on_hand):g} {matched_product.unit}\n"
                f"• Selling Price: ₹{float(matched_product.sell_price):.2f} (MRP: ₹{float(matched_product.mrp or matched_product.sell_price):.2f})\n"
                f"• GST Slab: {float(matched_product.gst_slab):g}%\n"
                f"• Barcode: {matched_product.barcode or barcode or '—'}"
            ),
        })

    # If product is not in catalog yet:
    return ok({
        "status": "NEW_PRODUCT_SUGGESTION",
        "detected": detected,
        "suggested_product": {
            "name": name,
            "brand": brand,
            "unit": unit,
            "mrp": float(mrp) if mrp else None,
            "sell_price": float(mrp) if mrp else 0.0,
            "cost_price": round(float(mrp) * 0.82, 2) if mrp else 0.0,
            "gst_slab": suggested_gst,
            "barcode": barcode,
            "hsn_code": detected.get("hsn_code"),
        },
        "message": (
            f"✨ Identified New Item: **{brand} {name}** ({unit})\n"
            f"• Detected Barcode: `{barcode or 'N/A'}`\n"
            f"• Estimated MRP: ₹{mrp or '—'}\n"
            f"• Suggested GST: {suggested_gst}%\n"
            f"Would you like me to add this product to your catalog?"
        ),
    })


# ── Tool: lookup_by_barcode ────────────────────────────────────────────────────

async def lookup_by_barcode(barcode: str) -> dict[str, Any]:
    """
    Look up a product in the store catalog by exact barcode number.

    Args:
        barcode: Barcode digits (EAN-13, UPC, etc.)

    Returns: ok({product: {...}}) or err(PRODUCT_NOT_FOUND)
    """
    clean_barcode = barcode.strip()
    async with get_db() as db:
        res = await db.execute(
            select(Product).where(
                Product.shop_id == SHOP_ID,
                Product.is_active == True,
                Product.barcode == clean_barcode,
            )
        )
        product = res.scalar_one_or_none()
        if not product:
            return err(
                "BARCODE_NOT_FOUND",
                f"No active product found with barcode '{clean_barcode}'. "
                "Use identify_product_from_image or add_product to register it.",
            )

        return ok({
            "product": _product_to_dict(product),
            "message": f"Found: {product.display_name} (Stock: {float(product.qty_on_hand):g} {product.unit}, Price: ₹{float(product.sell_price):.2f})",
        })
