---
name: analytics
description: >
  Business analytics and reporting for the kirana store.
  Daily close reports, sales summaries, GST collection breakdowns by slab.
  All computations run in Postgres — no client-side aggregation.
---

# Analytics Skill

## Overview
Three analytics tools power the store's reporting needs. All queries run in
Postgres for accuracy. Always offer to generate a PPTX deck after showing numbers.

## Tools

### `daily_close(target_date?)`
**The end-of-day report.** Shows:
- Total revenue and bill count
- GST collected (CGST + SGST separately)
- Payment mode breakdown (CASH vs UPI vs CREDIT vs CARD)
- Top 5 products by revenue
- Total new customer credit today

Default: today's date. Pass `target_date="2024-01-15"` for a specific date.

### `sales_summary(period)`
Summary for a wider period:
- `"today"` — just today
- `"week"` — last 7 days
- `"month"` — calendar month to date
- `"year"` — year to date

Returns totals + daily breakdown for charting.

### `gst_collected(period, by_slab=True)`
GST report for compliance and filing:
- Total CGST and SGST collected
- Breakdown by slab (0%, 5%, 12%, 18%, 28%)
- Taxable value per slab

## Common Patterns

**End of day close:**
```
User: "Close for today" / "Show today's report" / "Aaj ka hisaab"
1. daily_close()
2. Show summary in formatted message
3. Offer: "Would you like me to generate an analysis deck?"
   → generate_analysis_deck("today")
```

**Weekly review:**
```
User: "How was this week's sales?"
1. sales_summary("week")
2. Show trends, compare to previous if asked
3. Offer: "Generate this week's PPTX deck?"
   → generate_analysis_deck("week")
```

**GST filing preparation:**
```
User: "What GST did we collect this month?"
1. gst_collected("month", by_slab=True)
2. Show CGST/SGST per slab
3. "Total GST to file: ₹XXX (CGST: ₹X, SGST: ₹X)"
```

## Output Format

**Daily Close Summary:**
```
📊 Daily Close — 07 Sep 2024

💰 Revenue: ₹12,450
🧾 Bills: 47 | Avg: ₹264.89

💳 Payment Breakdown:
  CASH: ₹8,200 (28 bills)
  UPI: ₹3,750 (17 bills)
  CREDIT: ₹500 (2 bills)

🏷️ GST Collected:
  CGST: ₹285.50 | SGST: ₹285.50

🥇 Top Products:
  1. Aashirvaad Atta — 120kg — ₹6,000
  2. Saffola Oil — 45L — ₹3,825
  3. Tata Salt — 80kg — ₹2,400
```
