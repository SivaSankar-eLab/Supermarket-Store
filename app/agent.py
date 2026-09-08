"""
KiranaBot — Agent Dispatcher

This module is the public API for the Telegram bridge.
It owns:
  - TOOL_FUNCTIONS  — single registry of all 28 tool callables
  - TOOLS_SCHEMA    — single list of tool schemas (Anthropic format;
                       GeminiProvider converts these at init time)
  - build_system_prompt — shared prompt builder injected into both providers
  - KiranaBotAgent  — thin dispatcher that reads the ai_provider preference
                       and routes to the correct AbstractProvider

Business logic lives in app/tools/. Hooks live in app/hooks.py.
Neither is duplicated here.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

# ── Import all tool functions ─────────────────────────────────────────────────
from app.tools.inventory import (
    find_product, get_stock, list_low_stock, add_product,
    receive_stock, adjust_stock, list_products, update_product_price,
    list_batches_fefo,
)
from app.tools.billing import (
    start_bill, add_bill_item, update_bill_item, remove_bill_item,
    get_draft_bill, finalize_bill, void_bill, list_bills,
)
from app.tools.credit import (
    add_customer, find_customer, get_customer_balance,
    add_credit, record_payment, list_customers_with_dues, get_customer_statement,
    create_payment_reminder,
)
from app.tools.analytics import daily_close, sales_summary, gst_collected, reorder_suggestions
from app.tools.documents import generate_invoice_pdf, generate_analysis_deck
from app.tools.preferences import set_preference, get_preference, list_preferences
from app.tools.vision import identify_product_from_image, lookup_by_barcode

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Tool registry (single source of truth for all providers) ──────────────────
TOOL_FUNCTIONS: dict[str, Any] = {
    # Inventory
    "find_product": find_product,
    "get_stock": get_stock,
    "list_low_stock": list_low_stock,
    "add_product": add_product,
    "receive_stock": receive_stock,
    "adjust_stock": adjust_stock,
    "list_products": list_products,
    "update_product_price": update_product_price,
    "lookup_by_barcode": lookup_by_barcode,
    "list_batches_fefo": list_batches_fefo,
    # Vision & Barcode Scanning
    "identify_product_from_image": identify_product_from_image,
    # Billing
    "start_bill": start_bill,
    "add_bill_item": add_bill_item,
    "update_bill_item": update_bill_item,
    "remove_bill_item": remove_bill_item,
    "get_draft_bill": get_draft_bill,
    "finalize_bill": finalize_bill,
    "void_bill": void_bill,
    "list_bills": list_bills,
    # Khata
    "add_customer": add_customer,
    "find_customer": find_customer,
    "get_customer_balance": get_customer_balance,
    "add_credit": add_credit,
    "record_payment": record_payment,
    "list_customers_with_dues": list_customers_with_dues,
    "get_customer_statement": get_customer_statement,
    "create_payment_reminder": create_payment_reminder,
    # Analytics
    "daily_close": daily_close,
    "sales_summary": sales_summary,
    "gst_collected": gst_collected,
    "reorder_suggestions": reorder_suggestions,
    # Documents
    "generate_invoice_pdf": generate_invoice_pdf,
    "generate_analysis_deck": generate_analysis_deck,
    # Preferences
    "set_preference": set_preference,
    "get_preference": get_preference,
    "list_preferences": list_preferences,
}

# ── Tool schemas (Anthropic format — GeminiProvider converts at init) ─────────
TOOLS_SCHEMA: list[dict] = [
    # ── Vision & Barcode Scanning ──────────────────────────────────────────
    {
        "name": "identify_product_from_image",
        "description": "Analyze a product photo, packaging label, barcode image, or receipt. Extracts brand, item name, net quantity/unit, barcode number, MRP, and matches it against the store catalog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Absolute or relative file path to the image"},
                "context": {"type": "string", "description": "Optional user hint (e.g. 'received 10 packets', 'add to Ravi bill')"},
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "lookup_by_barcode",
        "description": "Look up a product in the store catalog by exact barcode number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "barcode": {"type": "string", "description": "Barcode numbers (EAN-13, UPC, etc.)"},
            },
            "required": ["barcode"],
        },
    },
    # ── Inventory ──────────────────────────────────────────────────────────
    {
        "name": "find_product",
        "description": "Fuzzy-search products by name or brand. Always call this first before add_bill_item or get_stock. Returns top candidates for disambiguation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Product name or brand to search for"},
                "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_stock",
        "description": "Get current stock details for a product by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "UUID of the product"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "list_low_stock",
        "description": "List all products where qty_on_hand <= reorder_level.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_product",
        "description": "Add a new product to the catalog with GST metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "unit": {"type": "string", "description": "kg/g/l/ml/pkt/doz/pc/box"},
                "gst_slab": {"type": "number", "description": "0, 5, 12, 18, or 28"},
                "cost_price": {"type": "number"},
                "sell_price": {"type": "number"},
                "brand": {"type": "string"},
                "is_loose": {"type": "boolean"},
                "hsn_code": {"type": "string"},
                "mrp": {"type": "number"},
                "initial_qty": {"type": "number", "default": 0},
                "reorder_level": {"type": "number", "default": 0},
                "barcode": {"type": "string", "description": "Barcode digits or numbers (optional)"},
            },
            "required": ["name", "unit", "gst_slab", "cost_price", "sell_price"],
        },
    },
    {
        "name": "receive_stock",
        "description": "Record a stock receipt/purchase. Updates cost_price and qty_on_hand.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "qty": {"type": "number"},
                "cost_price": {"type": "number"},
                "mrp": {"type": "number"},
                "note": {"type": "string"},
            },
            "required": ["product_id", "qty", "cost_price"],
        },
    },
    {
        "name": "adjust_stock",
        "description": "Manual stock adjustment (damage, theft, count correction). Reason is REQUIRED.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "delta": {"type": "number", "description": "Positive to add, negative to reduce"},
                "reason": {"type": "string", "description": "REQUIRED: why the adjustment is being made"},
            },
            "required": ["product_id", "delta", "reason"],
        },
    },
    {
        "name": "list_products",
        "description": "List all products in the catalog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "active_only": {"type": "boolean", "default": True},
            },
            "required": [],
        },
    },
    {
        "name": "update_product_price",
        "description": "Update sell_price, cost_price, or MRP for a product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "sell_price": {"type": "number"},
                "cost_price": {"type": "number"},
                "mrp": {"type": "number"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "list_batches_fefo",
        "description": "List product batches prioritized by Expiry Date (FEFO - First Expired, First Out) for waste reduction and discount prioritization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Optional product UUID"},
                "days_threshold": {"type": "integer", "description": "Days to expiry threshold (default 30)", "default": 30},
            },
            "required": [],
        },
    },
    # ── Billing ────────────────────────────────────────────────────────────
    {
        "name": "start_bill",
        "description": "Start a new DRAFT bill. Stock is not touched until finalize_bill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "UUID of customer (optional for walk-in)"},
            },
            "required": [],
        },
    },
    {
        "name": "add_bill_item",
        "description": "Add a product to a DRAFT bill. Use find_product first to get product_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "string"},
                "product_id": {"type": "string"},
                "qty": {"type": "number"},
            },
            "required": ["bill_id", "product_id", "qty"],
        },
    },
    {
        "name": "update_bill_item",
        "description": "Change the quantity of an item in a DRAFT bill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "qty": {"type": "number"},
            },
            "required": ["item_id", "qty"],
        },
    },
    {
        "name": "remove_bill_item",
        "description": "Remove an item from a DRAFT bill.",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "get_draft_bill",
        "description": "Show current state of a bill with all items and GST totals.",
        "input_schema": {
            "type": "object",
            "properties": {"bill_id": {"type": "string"}},
            "required": ["bill_id"],
        },
    },
    {
        "name": "finalize_bill",
        "description": "FINALIZE a DRAFT bill: checks stock, computes GST, deducts stock, records payment. Idempotent via idempotency_key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "string"},
                "payment_mode": {"type": "string", "description": "CASH | UPI | CREDIT | CARD"},
                "idempotency_key": {"type": "string", "description": "Unique key to prevent double-finalization"},
                "payment_ref": {"type": "string", "description": "UPI txn ID or card ref (optional)"},
            },
            "required": ["bill_id", "payment_mode", "idempotency_key"],
        },
    },
    {
        "name": "void_bill",
        "description": "Void a FINALIZED bill and reverse stock. Reason is REQUIRED.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["bill_id", "reason"],
        },
    },
    {
        "name": "list_bills",
        "description": "List recent bills, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "DRAFT | FINALIZED | VOID"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": [],
        },
    },
    # ── Khata ──────────────────────────────────────────────────────────────
    {
        "name": "add_customer",
        "description": "Add a new customer to the khata book.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "find_customer",
        "description": "Search for a customer by name or phone.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_customer_balance",
        "description": "Get outstanding khata balance for a customer. Balance = total_credit - total_payments.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "add_credit",
        "description": "Record goods given on credit (customer owes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number"},
                "ref_bill_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["customer_id", "amount"],
        },
    },
    {
        "name": "record_payment",
        "description": "Record a payment received from a customer against their khata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number"},
                "mode": {"type": "string", "description": "CASH | UPI | CARD"},
                "note": {"type": "string"},
            },
            "required": ["customer_id", "amount"],
        },
    },
    {
        "name": "list_customers_with_dues",
        "description": "List all customers with outstanding khata balance.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_customer_statement",
        "description": "Full transaction history for a customer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "create_payment_reminder",
        "description": "Generate a localized payment reminder message in English, Hindi, or Tamil with outstanding balance and UPI payment link.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer UUID"},
                "language": {"type": "string", "description": "english | hindi | tamil (default english)", "default": "english"},
                "upi_vpa": {"type": "string", "description": "Optional shop UPI ID"},
            },
            "required": ["customer_id"],
        },
    },
    # ── Analytics ──────────────────────────────────────────────────────────
    {
        "name": "daily_close",
        "description": "Daily close report: revenue, GST, top products, payment breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_date": {"type": "string", "description": "YYYY-MM-DD (default today)"},
            },
            "required": [],
        },
    },
    {
        "name": "sales_summary",
        "description": "Sales summary for a period: today | week | month | year.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "today | week | month | year"},
            },
            "required": [],
        },
    },
    {
        "name": "gst_collected",
        "description": "GST collection report, optionally by slab.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string"},
                "by_slab": {"type": "boolean", "default": True},
            },
            "required": [],
        },
    },
    {
        "name": "reorder_suggestions",
        "description": "Calculate daily sales velocity (units/day) for each product, estimated days of inventory remaining, and recommended reorder quantities based on supplier lead times.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "description": "Historical days to calculate sales velocity (default 14)", "default": 14},
                "lead_time_days": {"type": "integer", "description": "Supplier delivery lead time in days (default 3)", "default": 3},
            },
            "required": [],
        },
    },
    # ── Documents ──────────────────────────────────────────────────────────
    {
        "name": "generate_invoice_pdf",
        "description": "Generate a branded GST invoice PDF for a FINALIZED bill.",
        "input_schema": {
            "type": "object",
            "properties": {"bill_id": {"type": "string"}},
            "required": ["bill_id"],
        },
    },
    {
        "name": "generate_analysis_deck",
        "description": "Generate a PowerPoint (PPTX) business analytics deck analyzing store performance (sales revenue & daily trend chart, top selling items chart & volume, stock health & low-stock alerts, GST collected by slab chart, Khata receivables) with real charts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "today | week | month | year (default is week)"},
            },
            "required": [],
        },
    },
    # ── Preferences ────────────────────────────────────────────────────────
    {
        "name": "set_preference",
        "description": "Set a shop preference. Persists across sessions (survives /new).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"description": "Any JSON value (string, number, etc.)"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "get_preference",
        "description": "Get a single shop preference by key.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "list_preferences",
        "description": "List all configured shop preferences.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def build_system_prompt(preferences: dict[str, Any]) -> str:
    """Build the system prompt, injecting current shop preferences."""
    prefs_text = ""
    if preferences:
        prefs_lines = "\n".join(f"  {k}: {v}" for k, v in preferences.items())
        prefs_text = f"\n\nCurrent shop preferences:\n{prefs_lines}"

    ai_provider = preferences.get("ai_provider", "claude").capitalize()

    return f"""You are SupermarketBot — an AI operations assistant for a supermarket and retail grocery store.
You help the store manager manage inventory, billing, customer credit ledgers, and business analytics through Telegram.
Currently powered by: {ai_provider}

## Core Principles
1. **All business rules are in tools** — never invent prices, GST rates, or stock levels. Always call the appropriate tool.
2. **Fuzzy search first** — always call find_product or lookup_by_barcode before add_bill_item or any product operation.
3. **Photos & Barcodes** — when an image or barcode is provided, ALWAYS call identify_product_from_image or lookup_by_barcode. Strictly operate on the detected item (e.g. if image is Sugar, operate on Sugar; NEVER substitute with unrelated items).
4. **Confirm before finalizing** — always show the bill summary (get_draft_bill) and ask "Shall I finalize?" before calling finalize_bill.
5. **Structured refusals** — if a tool returns ok=false, relay the error clearly and suggest a fix.
6. **GST compliance** — always mention GST breakdown when discussing bills.
7. **Multilingual & Natural Language Support** — seamlessly understand queries in plain English or local phrasing.

## Workflow Patterns
- **Scan photo / Barcode**: identify_product_from_image(image_path) → if found in catalog, show stock/price and offer to bill/restock; if new, offer to add_product
- **New bill**: start_bill → add_bill_item (×N) → get_draft_bill → confirm → finalize_bill
- **Receive stock**: find_product / lookup_by_barcode → receive_stock
- **Check customer credit / Reminders**: find_customer → get_customer_balance → create_payment_reminder
- **Reorder Suggestions**: reorder_suggestions(lookback_days, lead_time_days) → compute sales velocity & stockout risk
- **FEFO Expiry Tracking**: list_batches_fefo → prioritize near-expiry batches
- **Daily close**: daily_close → offer to generate_analysis_deck
- **Generate invoice**: finalize_bill → generate_invoice_pdf (auto-attach PDF)
- **Generate PowerPoint / Analysis Deck**: when asked for a presentation, PowerPoint, PPTX, or store analysis → call generate_analysis_deck(period) (auto-attaches PPTX with real charts)
- **Switch AI**: Owner can say "AI Gemini" or "AI Claude" to switch providers

## Memory
Shop preferences persist across sessions. Even after /new, you remember the shop's settings
because they are loaded from the database, not from conversation history.{prefs_text}

Always be concise, helpful, and professional. Use ₹ for Indian Rupees."""


# ── Initialize providers once at module load ──────────────────────────────────
from app.providers import init_providers  # noqa: E402
init_providers(TOOLS_SCHEMA, build_system_prompt, TOOL_FUNCTIONS)


# ── SupermarketBotAgent: public API used by telegram_bridge ───────────────────

class SupermarketBotAgent:
    """
    Thin dispatcher. Reads the ai_provider preference on every message
    and routes to the appropriate AbstractProvider singleton.
    """

    async def process_message(
        self,
        chat_id: int,
        user_message: str,
        preferences: dict[str, Any],
    ) -> tuple[str, list[str]]:
        from app.providers import process_with_fallback
        provider_name = str(preferences.get("ai_provider", "claude")).lower()
        logger.info("Routing chat_id=%d to provider=%s", chat_id, provider_name)
        return await process_with_fallback(provider_name, chat_id, user_message, preferences)

    def reset_session(self, chat_id: int) -> None:
        """Reset session on all providers so /new is fully clean."""
        from app.providers import reset_all_sessions
        reset_all_sessions(chat_id)
        logger.info("All provider sessions reset for chat_id=%d", chat_id)


# Backwards compatibility alias
KiranaBotAgent = SupermarketBotAgent


# ── Singleton agent instance ──────────────────────────────────────────────────
_agent: SupermarketBotAgent | None = None


def get_agent() -> SupermarketBotAgent:
    global _agent
    if _agent is None:
        _agent = SupermarketBotAgent()
    return _agent
