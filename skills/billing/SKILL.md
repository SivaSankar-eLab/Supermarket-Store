---
name: billing
description: >
  Create, edit, and finalize customer bills with GST compliance.
  Handles multi-item bills, mid-build edits, payment modes, idempotent finalization,
  and PDF invoice generation.
---

# Billing Skill

## Overview
Bills follow a strict lifecycle: **DRAFT → FINALIZED → (optionally) VOID**

Stock is **never touched** until `finalize_bill` is called. This means:
- Users can build and edit bills freely without affecting stock
- A single atomic transaction handles stock deduction + bill finalization

## Bill Lifecycle

```
start_bill() → DRAFT bill created
  ↓
add_bill_item() × N → items added, GST pre-computed per line
  ↓
get_draft_bill() → show summary with totals
  ↓  (user confirms)
finalize_bill() → stock deducted, GST locked, bill FINALIZED
  ↓
generate_invoice_pdf() → PDF sent to user
```

## Tools

### `start_bill(customer_id?)`
Create a new DRAFT bill. Pass `customer_id` for named customer billing.
For walk-in customers, omit `customer_id`.

### `add_bill_item(bill_id, product_id, qty)`
Add a product to the draft. **Always call `find_product` first to get product_id.**
- If the product is already in the bill, it updates the quantity
- GST is pre-computed but not finalized until `finalize_bill`

### `update_bill_item(item_id, qty)`
Change quantity of an item in a draft bill. Re-computes GST automatically.

### `remove_bill_item(item_id)`
Remove an item from the draft entirely.

### `get_draft_bill(bill_id)`
Show the current draft with all items, per-line GST, and preview totals.
**Always show this to the user before asking to finalize.**

### `finalize_bill(bill_id, payment_mode, idempotency_key, payment_ref?)`
**THE CRITICAL CALL.** Atomically:
1. Checks stock sufficiency for every item
2. Computes final GST using Decimal arithmetic
3. Verifies grand_total >= aggregate cost
4. Deducts stock + inserts SALE movements
5. Marks bill FINALIZED

**Idempotency**: Generate `idempotency_key = f"bill_{bill_id}_{chat_id}"` — safe to retry.

Payment modes: `CASH | UPI | CREDIT | CARD`

### `void_bill(bill_id, reason)`
Void a finalized bill. Reverses stock via VOID_REVERSAL movements.
**Reason is REQUIRED.** Bill is preserved in ledger (never deleted).

### `list_bills(status?, limit=20)`
List recent bills. Filter by DRAFT | FINALIZED | VOID.

## Common Patterns

**Multi-item bill:**
```
User: "Bill for Ravi: 2kg atta, 1L oil, 500g sugar"
1. find_customer("Ravi") → customer_id
2. start_bill(customer_id)
3. find_product("atta") → add_bill_item(bill_id, product_id, 2)
4. find_product("oil") → add_bill_item(bill_id, product_id, 1)
5. find_product("sugar") → add_bill_item(bill_id, product_id, 0.5)
6. get_draft_bill(bill_id) → show summary
7. "Shall I finalize? Total ₹XXX via CASH?"
8. finalize_bill(bill_id, "CASH", f"bill_{bill_id}_{chat_id}")
9. generate_invoice_pdf(bill_id)
```

**Editing mid-build:**
```
User: "Actually make that 3kg atta, not 2"
→ update_bill_item(item_id, 3)  ← item_id from add_bill_item response
```

**Customer Credit billing:**
```
finalize_bill(bill_id, "CREDIT", idempotency_key)
→ automatically creates credit ledger entry
→ call add_credit(customer_id, grand_total, ref_bill_id=bill_id)
```

## GST Invoice Format
Invoice shows:
- Per-line: Product | HSN | Qty | Rate | Taxable | CGST% | CGST₹ | SGST% | SGST₹ | Total
- GST summary table grouped by slab
- Subtotal → CGST total → SGST total → Round off → **Grand Total**

## Error Responses
| error_code | Meaning | Action |
|---|---|---|
| INSUFFICIENT_STOCK | Stock too low to finalize | Tell user, ask to restock |
| BILL_NOT_DRAFT | Bill already finalized/void | Start a new bill |
| BILL_EMPTY | No items in bill | Add items first |
| SELL_BELOW_COST | Grand total < cost | Check prices |
