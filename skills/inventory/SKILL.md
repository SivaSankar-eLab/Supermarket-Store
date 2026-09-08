---
name: inventory
description: >
  Manage the kirana store product catalog and stock levels.
  Use these tools for receiving stock, adding new products, searching items,
  adjusting quantities, and monitoring reorder levels.
---

# Inventory Skill

## Overview
This skill handles all stock-related operations for the kirana store.
Use fuzzy product search before any operation — never assume a product ID.

## Tools

### `find_product(query, limit=5)`
**Always call this first.** Fuzzy-searches products by name or brand using Postgres pg_trgm.
- Returns a list of candidates ordered by similarity score
- If `auto_selected` is present, use that product without asking the user
- If multiple candidates and none auto-selected, show options and ask the user to confirm

### `get_stock(product_id)`
Get detailed stock info for a specific product. Use after find_product resolves the ID.

### `list_low_stock()`
Returns all products where `qty_on_hand <= reorder_level`. Use at the start of each day.

### `add_product(name, unit, gst_slab, cost_price, sell_price, ...)`
Add a new product. Required fields: name, unit, gst_slab (0/5/12/18/28), cost_price, sell_price.
- Always ask for HSN code if not provided
- Default gst_slab is 5 for food items unless specified

### `receive_stock(product_id, qty, cost_price, mrp?)`
Record a delivery/purchase. Updates both cost_price and qty_on_hand in one operation.

### `adjust_stock(product_id, delta, reason)`
For manual corrections (damage, theft, count errors). **Reason is REQUIRED.**
- Positive delta: found more stock
- Negative delta: writing off damaged/lost stock

### `list_products(active_only=True)`
Full catalog listing. Use when user asks "what do we have?" or "show all products."

### `update_product_price(product_id, sell_price?, cost_price?, mrp?)`
Update one or more prices. Blocks if sell_price would be below cost_price.

### `lookup_by_barcode(barcode)`
Direct product search by barcode / EAN-13 number.

### `identify_product_from_image(image_path, context?)`
Multimodal AI vision tool to identify grocery items, read packaging labels, barcodes, and MRP from images.

## Common Patterns

**User: "Add 50kg of Aashirvaad atta, bought at ₹42, selling at ₹50"**
```
1. find_product("Aashirvaad atta")
   → If not found: add_product("Atta", "kg", 0, 42, 50, brand="Aashirvaad", initial_qty=50)
   → If found: receive_stock(product_id, 50, 42)
```

**User: "What's the stock of oil?"**
```
1. find_product("oil") → show candidates, let user pick
2. get_stock(product_id)
```

**User: "2 bags of sugar were damaged"**
```
1. find_product("sugar")
2. adjust_stock(product_id, -2, "2 bags damaged/spoiled")
```

## Units Reference
| Unit | Description |
|------|-------------|
| kg | Kilograms (loose items like atta, rice, dal) |
| g | Grams |
| l | Litres (oil, milk) |
| ml | Millilitres |
| pkt | Packet |
| doz | Dozen |
| pc | Piece |
| box | Box |

## GST Slabs for Common Kirana Items
| Slab | Items |
|------|-------|
| 0% | Fresh vegetables, unpackaged grains |
| 5% | Packaged food (atta, rice, dal, oil, sugar, salt) |
| 12% | Ghee, butter, packaged spices |
| 18% | Soaps, shampoos, detergents |
| 28% | Luxury/tobacco goods |
