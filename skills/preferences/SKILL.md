---
name: preferences
description: >
  Manage shop preferences that persist across sessions.
  Preferences are stored in Postgres keyed by shop_id — NOT session_id.
  They survive /new and are automatically injected into every new session.
---

# Preferences Skill

## Overview
Preferences are the mechanism that makes **memory survive `/new`**.

When a user sends `/new`, the conversation history is cleared — but preferences
are read fresh from the database on every message, so they're always available.

**Key design**: Stored in `preferences` table, keyed by `shop_id` not `chat_id`
or session ID. This means preferences are shop-wide and permanent until changed.

## Tools

### `set_preference(key, value)`
Save a preference. Uses UPSERT — safe to call multiple times.

### `get_preference(key)`
Retrieve a single preference by key.

### `list_preferences()`
Show all configured preferences.

## Known Preference Keys

| Key | Description | Example Value |
|-----|-------------|---------------|
| `shop_name` | Display name on invoices | "Sharma Kirana Store" |
| `owner_name` | Owner's name | "Rajesh Sharma" |
| `gstin` | GST Identification Number | "27AABCU9603R1ZX" |
| `address` | Shop address on invoices | "123 MG Road, Mumbai" |
| `default_gst_slab` | Default slab for new products | 5 |
| `currency_symbol` | Currency symbol | "₹" |
| `invoice_footer` | Footer on invoices | "Thank you! Visit again." |
| `low_stock_alert_days` | Low stock threshold | 3 |
| `timezone` | Timezone for reports | "Asia/Kolkata" |
| `language` | Preferred language | "hinglish" |

## Common Patterns

**Setting up the store:**
```
User: "My shop name is Sharma Kirana Store"
→ set_preference("shop_name", "Sharma Kirana Store")

User: "My GSTIN is 27AABCU9603R1ZX"
→ set_preference("gstin", "27AABCU9603R1ZX")

User: "Address: 123 MG Road, Mumbai 400001"
→ set_preference("address", "123 MG Road, Mumbai 400001")
```

**After /new — preferences automatically restored:**
```
[User sends /new]
→ Session cleared
→ Next message: preferences re-injected from DB
→ Agent already knows shop_name, gstin, address, etc.
```

**Showing current settings:**
```
User: "What are my current settings?"
→ list_preferences()
→ Show as formatted list
```

## Implementation Note
The Telegram bridge calls `load_preferences_for_context()` at the start of
EVERY message processing cycle. This ensures:
1. A new `/new` session gets all preferences immediately
2. Preferences changed in the current session are visible in the next message
3. No stale data — always fresh from DB
