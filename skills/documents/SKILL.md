---
name: documents
description: >
  Generate professional documents: branded PDF GST invoices and business
  analytics PPTX presentations. Files are automatically sent as attachments
  in the Telegram chat after generation.
---

# Documents Skill

## Overview
Two document generation tools produce real files that are sent to the user via Telegram.

## Tools

### `generate_invoice_pdf(bill_id)`
Generates a branded GST invoice PDF from a FINALIZED bill.

**When to call:**
- After any successful `finalize_bill` call — offer automatically
- When user says "send invoice", "invoice bhejo", "PDF chahiye"

**What it generates:**
- Shop header: name, GSTIN, address
- Bill details: date, bill ID, customer name/phone
- Line-item table: Product | HSN | Qty | Unit | Rate | Taxable | CGST | SGST | Total
- GST summary table grouped by slab
- Total section: Subtotal → CGST → SGST → Round-off → **Grand Total** (in bold)
- Payment mode and reference
- "Thank you" footer (customizable via preferences)

**Tech:** Jinja2 HTML template → WeasyPrint PDF

### `generate_analysis_deck(period)`
Generates a comprehensive, branded 7-slide business analytics PPTX presentation with real charts.

**Periods:** `"today"` | `"week"` | `"month"` | `"year"`

**Slides generated:**
1. **Executive Cover & Performance Overview**: Store name, period badge, date range, 4 key highlight pill cards.
2. **Sales & Financial KPIs**: 6 Key Metric cards (Gross Revenue, Bills Finalized, Daily Run-rate, Avg Bill Value, GST Collected, Customer Credit Balance) + insights.
3. **Sales Velocity & Daily Revenue Trend**: Real Matplotlib Bar Chart of daily sales volume with value annotations + Peak/Lowest day stats.
4. **Top Performing Products**: Real Matplotlib Horizontal Bar Chart of top 5-7 products by sales revenue + Products breakdown table (units sold & revenue).
5. **Stock Health & Inventory Status**: Real Matplotlib Donut Chart of stock distribution (Healthy vs Low Stock vs Out of Stock) + Critical low-stock reorder alert table.
6. **GST Collection & Tax Compliance**: Real Matplotlib Pie Chart of GST collections by slab (0%, 5%, 12%, 18%, 28%) + CGST/SGST matrix & turnover table.
7. **Customer Credit Receivables & Payment Channels**: Total credit balance, payment mode distribution (Cash, UPI, Credit), and top debtors list.

**When to call:**
- When user asks for "PowerPoint", "PPTX", "presentation", "analysis deck", "report", "store performance deck", "sales analysis"
- After `daily_close` — proactively offer the deck

**Tech:** Matplotlib (high-resolution dark-theme charts) → python-pptx

## Workflow

```
Billing complete:
  finalize_bill(...)  →  "Bill finalized! Want me to send the invoice PDF?"
  User: "Yes" → generate_invoice_pdf(bill_id)  →  [PDF sent automatically]

End of day:
  daily_close()  →  "Want an analysis deck for today?"
  User: "Yes" → generate_analysis_deck("today")  →  [PPTX sent automatically]
```

## Notes
- Files are generated server-side and auto-attached in the Telegram reply
- No need to explain the process — just say "Here's your invoice! 📄"
- Invoice filename: `invoice_XXXXXXXX.pdf`
- Deck filename: `analysis_week_2024-09-07.pptx`
