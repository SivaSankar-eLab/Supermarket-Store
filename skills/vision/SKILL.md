---
name: vision
description: >
  Identify grocery products, read packaging labels, scan barcodes/QR codes,
  and match items against the store catalog using Multimodal AI Vision (Gemini / Claude).
---

# Vision & Barcode Identification Skill

## Overview
This skill empowers the KiranaBot agent to process product packaging images, price tags, shelf photos, and barcodes sent via Telegram or uploaded on the Web Dashboard. It performs OCR, brand & SKU recognition, weight/unit extraction, and cross-references PostgreSQL catalog to either match stock or suggest 1-click registration of new SKUs.

## Tools

### `identify_product_from_image(image_path, context="")`
Analyzes an image containing product packaging, a price tag, or a barcode label using Google Gemini / Claude Vision.
- Extracts: `brand`, `name`, `net_qty`, `unit` (kg/g/l/ml/pkt/pc/doz/box), `barcode`, `mrp`, `category`, `suggested_gst_slab`, `confidence`.
- Cross-references catalog:
  1. Checks exact match on `barcode` column in `products`.
  2. Falls back to `pg_trgm` fuzzy matching on `brand + name`.
- Returns:
  - `status: "MATCHED_IN_CATALOG"`: Item exists. Provides current on-hand stock, selling price, MRP, GST slab.
  - `status: "NEW_PRODUCT_SUGGESTION"`: Item is new. Provides pre-filled metadata and suggests calling `add_product`.

### `lookup_by_barcode(barcode)`
Performs an instant direct lookup of a product by its exact barcode or EAN-13 string.
- Returns product stock, unit, selling price, and GST details if found.
- If not found, recommends scanning the packaging photo or using `add_product`.

## Telegram Workflow
1. User sends a photo or document on Telegram (with or without caption, e.g. "Add 20 packets to stock").
2. The Telegram poller / webhook downloads the high-resolution image to `docs_output/scans/<file_id>.jpg`.
3. The bridge injects `[User sent product photo: image_path='...']` into the message.
4. Agent invokes `identify_product_from_image(image_path)`.
5. If matched, agent responds with stock level and proceeds with user's intent (e.g., adding to bill or restock).
6. If not matched, agent presents the extracted product details and asks the owner if they wish to add it to catalog.

## Dashboard Workflow
1. Navigate to the **Vision & Barcode** tab on the Web Dashboard (`/dashboard`).
2. Drop or upload packaging photos, or type a barcode number.
3. Click **Identify Product & Match Catalog**.
4. View instant real-time AI recognition results:
   - For matched products: Live on-hand stock status & price.
   - For new products: Pre-filled registration form with 1-click **Add to Store Catalog** button.
