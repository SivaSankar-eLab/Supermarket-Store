"""
KiranaBot — Preferences Tools

Shop preferences are stored in Postgres keyed by shop_id — NOT session_id.
This is what makes memory survive /new: a fresh session gets the same preferences
injected because they're read from the DB, not from conversation state.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.models import Preference
from app.tools import ok, err
from app.config import get_settings

settings = get_settings()
SHOP_ID = uuid.UUID(settings.shop_id)

# Predefined preference keys with descriptions
KNOWN_PREFERENCES = {
    "shop_name": "Display name of the shop",
    "owner_name": "Shop owner's name",
    "gstin": "GST Identification Number",
    "address": "Shop address shown on invoices",
    "default_gst_slab": "Default GST slab for new products (0/5/12/18/28)",
    "currency_symbol": "Currency symbol (default ₹)",
    "invoice_footer": "Custom footer text on invoices",
    "low_stock_alert_days": "Days of stock considered 'low'",
    "timezone": "Timezone for reports (e.g., Asia/Kolkata)",
    "language": "Response language preference",
}


# ── Tool: set_preference ───────────────────────────────────────────────────────

async def set_preference(key: str, value: Any) -> dict[str, Any]:
    """
    Set a shop preference. Preferences persist across sessions — they survive /new.
    Stored in Postgres keyed by shop_id, not session_id.

    Args:
        key: Preference key (e.g., "shop_name", "gstin", "invoice_footer")
        value: Value to store (string, number, or dict)

    Returns: ok({preference: {...}}) or err
    """
    if not key or not key.strip():
        return err("INVALID_KEY", "Preference key cannot be empty.")

    async with get_db() as db:
        # Upsert: insert or update on conflict
        stmt = (
            pg_insert(Preference)
            .values(
                shop_id=SHOP_ID,
                key=key.strip(),
                value={"v": value} if not isinstance(value, dict) else value,
            )
            .on_conflict_do_update(
                index_elements=["shop_id", "key"],
                set_={"value": {"v": value} if not isinstance(value, dict) else value},
            )
            .returning(Preference)
        )
        result = await db.execute(stmt)
        pref = result.scalar_one()

        return ok({
            "key": pref.key,
            "value": pref.value.get("v", pref.value) if "v" in pref.value else pref.value,
            "message": f"✅ Preference '{key}' saved.",
        })


# ── Tool: get_preference ───────────────────────────────────────────────────────

async def get_preference(key: str) -> dict[str, Any]:
    """
    Get a single preference value by key.

    Args:
        key: Preference key

    Returns: ok({key: ..., value: ...}) or err if not set
    """
    async with get_db() as db:
        result = await db.execute(
            select(Preference).where(
                Preference.shop_id == SHOP_ID,
                Preference.key == key.strip(),
            )
        )
        pref = result.scalar_one_or_none()
        if not pref:
            return err(
                "PREFERENCE_NOT_SET",
                f"Preference '{key}' is not set. Use set_preference to configure it.",
            )
        val = pref.value.get("v", pref.value) if "v" in pref.value else pref.value
        return ok({"key": pref.key, "value": val})


# ── Tool: list_preferences ─────────────────────────────────────────────────────

async def list_preferences() -> dict[str, Any]:
    """
    List all configured shop preferences.

    Returns: ok({preferences: {key: value, ...}})
    """
    async with get_db() as db:
        result = await db.execute(
            select(Preference).where(Preference.shop_id == SHOP_ID).order_by(Preference.key)
        )
        prefs = result.scalars().all()
        prefs_dict = {
            p.key: p.value.get("v", p.value) if "v" in p.value else p.value
            for p in prefs
        }
        return ok({
            "preferences": prefs_dict,
            "count": len(prefs_dict),
        })


# ── Helper: load_preferences_for_context ──────────────────────────────────────

async def load_preferences_for_context() -> dict[str, Any]:
    """
    Load all preferences and return as a flat dict for injecting into agent context.
    Called by the Telegram bridge at the start of every session.
    """
    async with get_db() as db:
        result = await db.execute(
            select(Preference).where(Preference.shop_id == SHOP_ID)
        )
        prefs = result.scalars().all()
        return {
            p.key: p.value.get("v", p.value) if "v" in p.value else p.value
            for p in prefs
        }
