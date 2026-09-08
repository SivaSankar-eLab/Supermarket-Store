---
name: credit_ledger
description: >
  Manage the customer credit ledger. Track credit given, payments received,
  and outstanding balances. Balance is always computed from the event ledger —
  never stored as a mutable column.
---

# Customer Credit Ledger Skill

## Overview
The customer credit ledger is implemented as an **event-sourced append-only ledger**:

```
balance = SUM(CREDIT transactions) - SUM(PAYMENT transactions)
```

This is never stored as a mutable column — it is always computed live from the transaction history.
Benefits:
- Impossible to corrupt the balance
- Full audit trail of every transaction
- Can reconstruct balance at any point in time

## Tools

### `add_customer(name, phone?)`
Register a new customer. Phone is optional but strongly recommended for deduplication.

### `find_customer(query)`
Search by name or phone number. Returns matching customers.

### `get_customer_balance(customer_id)`
Returns current balance, balance label (outstanding/advance), and last 10 transactions.
- Positive balance = customer owes money (most common)
- Negative balance = you owe the customer (overpaid)
- Zero = all settled

### `add_credit(customer_id, amount, ref_bill_id?, note?)`
Record that goods were given on credit. Usually called automatically when
`finalize_bill` is called with `payment_mode="CREDIT"`.

### `record_payment(customer_id, amount, mode="CASH", note?)`
Record a payment received from the customer.
- Warns if payment exceeds outstanding balance (records as advance)
- Modes: CASH | UPI | CARD

### `list_customers_with_dues()`
Shows all customers with outstanding balance > 0, sorted by amount owed (highest first).

### `get_customer_statement(customer_id, limit=50)`
Full chronological transaction history for a customer — like an account statement.

## Common Patterns

**Customer takes goods on credit:**
```
User: "Ravi took goods worth ₹500 on credit"
1. find_customer("Ravi")
2. add_credit(customer_id, 500, note="Goods taken on credit")
3. Report: "Ravi now owes ₹XXX total"
```

**Customer pays back:**
```
User: "Ravi paid ₹200 via UPI"
1. find_customer("Ravi")
2. record_payment(customer_id, 200, "UPI")
3. Report: "Payment recorded. Remaining balance: ₹XXX"
```

**Check who owes money:**
```
User: "Who all has pending dues?"
1. list_customers_with_dues()
2. Show formatted table with name and balance
```

**Full credit bill workflow:**
```
User: "Make a bill for Ravi: 2kg flour — he'll pay later"
1. find_customer("Ravi") → customer_id
2. start_bill(customer_id)
3. [add items...]
4. finalize_bill(bill_id, "CREDIT", idempotency_key)
5. add_credit(customer_id, grand_total, ref_bill_id=bill_id)
6. "Bill added to Ravi's credit account. He now owes ₹XXX."
```

## Balance Interpretation
```
Ravi's Credit Statement:
  Date        | Type    | Amount | Running Balance
  ────────────────────────────────────────────────
  01-Sep      | CREDIT  | ₹500   | ₹500 (owes)
  03-Sep      | CREDIT  | ₹300   | ₹800 (owes)
  05-Sep      | PAYMENT | ₹400   | ₹400 (owes)
  07-Sep      | PAYMENT | ₹400   | ₹0   (settled!)
```
