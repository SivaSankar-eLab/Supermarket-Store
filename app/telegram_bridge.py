"""
KiranaBot — Telegram Bridge

Responsibilities:
  1. Receive webhook updates from Telegram
  2. DEDUPE: check processed_telegram_updates by update_id → drop if already seen
  3. INSERT update_id into processed_telegram_updates
  4. Resolve chat_id → shop_id → load preferences fresh from DB (not from session)
  5. Forward message to Claude Agent SDK
  6. Send reply text + attach any generated PDFs/PPTX as documents

This layer contains ZERO business logic — it's a thin routing layer only.
"""
from __future__ import annotations

import re

import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Header
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import get_db
from app.models import ProcessedTelegramUpdate, Shop
from app.agent import get_agent
from app.tools.preferences import load_preferences_for_context
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter()

TELEGRAM_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


# ── Telegram API helpers ──────────────────────────────────────────────────────

async def send_message(chat_id: int, text: str) -> None:
    """Send a text message to a Telegram chat."""
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{TELEGRAM_BASE}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text[:4096],  # Telegram max
                "parse_mode": "Markdown",
            },
        )


async def send_document(chat_id: int, file_path: str, caption: str = "") -> None:
    """Send a file (PDF/PPTX) as a document to a Telegram chat."""
    path = Path(file_path)
    if not path.exists():
        logger.warning("Document file not found: %s", file_path)
        return

    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            await client.post(
                f"{TELEGRAM_BASE}/sendDocument",
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"document": (path.name, f)},
            )


async def send_typing(chat_id: int) -> None:
    """Show typing indicator while processing."""
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{TELEGRAM_BASE}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
        )


async def download_telegram_file(file_id: str, dest_dir: Path | None = None) -> Path:
    """Download a photo or document file from Telegram by file_id and return local path."""
    import uuid
    dest = dest_dir or Path("docs_output/scans")
    dest.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=35) as client:
        info_resp = await client.get(f"{TELEGRAM_BASE}/getFile", params={"file_id": file_id})
        info_data = info_resp.json()
        if not info_data.get("ok"):
            raise RuntimeError(f"Telegram getFile failed: {info_data}")

        file_path = info_data["result"]["file_path"]
        ext = Path(file_path).suffix or ".jpg"
        local_filename = f"scan_{uuid.uuid4().hex[:8]}{ext}"
        local_target = dest / local_filename

        download_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
        file_resp = await client.get(download_url)
        if file_resp.status_code != 200:
            raise RuntimeError(f"Failed to download Telegram media: status {file_resp.status_code}")

        with open(local_target, "wb") as f:
            f.write(file_resp.content)

        return local_target.resolve()


# ── Deduplication ─────────────────────────────────────────────────────────────

async def is_duplicate_update(update_id: int, chat_id: int) -> bool:
    """
    Check if update_id was already processed.
    If not, insert it atomically (returns False = "not a duplicate, process it").
    Uses INSERT ... ON CONFLICT DO NOTHING to handle race conditions.
    """
    async with get_db() as db:
        # Try to insert — if the row exists (UNIQUE violation), do nothing
        result = await db.execute(
            insert(ProcessedTelegramUpdate)
            .values(update_id=update_id, chat_id=chat_id)
            .on_conflict_do_nothing(index_elements=["update_id"])
            .returning(ProcessedTelegramUpdate.update_id)
        )
        inserted = result.scalar_one_or_none()
        return inserted is None  # None = conflict = already processed


# ── Shop resolution ───────────────────────────────────────────────────────────

async def ensure_shop_exists(chat_id: int) -> None:
    """
    Auto-register a shop for a new chat_id if it doesn't exist.
    In single-shop mode, uses the configured SHOP_ID.
    """
    import uuid
    async with get_db() as db:
        result = await db.execute(
            select(Shop).where(Shop.chat_id == chat_id)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            # Check if default shop exists without chat_id
            default_result = await db.execute(
                select(Shop).where(Shop.id == uuid.UUID(settings.shop_id))
            )
            default_shop = default_result.scalar_one_or_none()
            if default_shop:
                default_shop.chat_id = chat_id
                logger.info("Linked chat_id=%d to existing shop", chat_id)
            else:
                # Create the shop
                shop = Shop(
                    id=uuid.UUID(settings.shop_id),
                    name=settings.shop_name,
                    owner_name=settings.shop_owner_name,
                    gstin=settings.shop_gstin or None,
                    address=settings.shop_address or None,
                    chat_id=chat_id,
                )
                db.add(shop)
                logger.info("Created new shop for chat_id=%d", chat_id)


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict:
    """
    Main Telegram webhook endpoint.
    Security: validates X-Telegram-Bot-Api-Secret-Token header.
    """
    # Validate webhook secret
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body: dict = await request.json()
    update_id: int = body.get("update_id", 0)
    message: dict = body.get("message") or body.get("edited_message") or {}

    if not message:
        return {"ok": True}  # Ignore non-message updates (callbacks, etc.)

    chat_id: int = message.get("chat", {}).get("id", 0)
    text: str = (message.get("text") or "").strip()
    caption: str = (message.get("caption") or "").strip()
    photo = message.get("photo")
    document = message.get("document")

    image_prompt = None
    if photo and isinstance(photo, list) and len(photo) > 0:
        file_id = photo[-1]["file_id"]
        try:
            downloaded_path = await download_telegram_file(file_id)
            hint = caption if caption else "Identify this product or barcode, check catalog stock, and suggest next actions."
            image_prompt = f"[User sent product photo: image_path='{downloaded_path.as_posix()}'] {hint}"
        except Exception as dl_err:
            logger.error("Failed to download Telegram photo: %s", dl_err)
            await send_message(chat_id, "⚠️ Failed to download photo. Please try again.")
            return {"ok": True}
    elif document and str(document.get("mime_type", "")).startswith("image/"):
        file_id = document["file_id"]
        try:
            downloaded_path = await download_telegram_file(file_id)
            hint = caption if caption else "Identify this product or barcode, check catalog stock, and suggest next actions."
            image_prompt = f"[User sent product photo: image_path='{downloaded_path.as_posix()}'] {hint}"
        except Exception as dl_err:
            logger.error("Failed to download Telegram image doc: %s", dl_err)
            await send_message(chat_id, "⚠️ Failed to download document image. Please try again.")
            return {"ok": True}

    user_query = image_prompt if image_prompt else (text or caption)
    if not chat_id or not user_query:
        return {"ok": True}

    # ── Step 1: Dedup ─────────────────────────────────────────────────────────
    if await is_duplicate_update(update_id, chat_id):
        logger.info("Duplicate update_id=%d — skipping", update_id)
        return {"ok": True}

    # ── Step 2: Ensure shop exists ────────────────────────────────────────────
    await ensure_shop_exists(chat_id)

    # ── Step 3: Handle /new command (session reset) ───────────────────────────
    if user_query.lower() in {"/new", "/start"}:
        get_agent().reset_session(chat_id)
        await send_message(
            chat_id,
            "🔄 *New session started!*\n\n"
            "Your shop preferences are still remembered.\n"
            "How can I help you today?",
        )
        return {"ok": True}

    # ── Step 4: Handle /help ──────────────────────────────────────────────────
    if user_query.lower() == "/help":
        await send_message(
            chat_id,
            "🏪 *Supermarket Bot Commands*\n\n"
            "📦 *Inventory*\n"
            "• 'What's the stock of wheat flour?'\n"
            "• 'Add 50kg Aashirvaad flour at ₹42, sell at ₹50'\n"
            "• 'Show low stock items'\n\n"
            "🧾 *Billing*\n"
            "• 'New bill for Ravi: 2kg flour, 1L oil'\n"
            "• 'Finalize bill via UPI'\n"
            "• 'Generate invoice for last bill'\n\n"
            "📒 *Customer Credit (Ledger)*\n"
            "• 'Ravi took ₹500 on credit'\n"
            "• 'How much does Ravi owe?'\n"
            "• 'Ravi paid ₹200'\n\n"
            "📊 *Reports*\n"
            "• 'Show today's close'\n"
            "• 'Generate this week's analysis deck'\n\n"
            "⚙️ *Settings*\n"
            "• 'Set shop name to ABC Stores'\n"
            "• 'AI Gemini' — switch to Gemini AI\n"
            "• 'AI Claude' — switch to Claude AI\n\n"
            "/new — Start fresh session\n"
            "/help — Show this message",
        )
        return {"ok": True}

    # ── Step 4b: Handle AI provider switching (free — no LLM call) ───────────
    _provider_match = re.match(r"^ai\s+(claude|gemini)$", text.strip(), re.IGNORECASE)
    if _provider_match:
        new_provider = _provider_match.group(1).lower()
        from app.tools.preferences import set_preference
        await set_preference(key="ai_provider", value=new_provider)
        emoji = "🤖" if new_provider == "gemini" else "🧠"
        await send_message(
            chat_id,
            f"{emoji} *Switched to {new_provider.capitalize()}!*\n"
            f"All future messages will be processed by {new_provider.capitalize()}.\n"
            f"This preference is saved — it survives /new.",
        )
        logger.info("AI provider switched to '%s' for chat_id=%d", new_provider, chat_id)
        return {"ok": True}

    # ── Step 5: Show typing indicator ─────────────────────────────────────────
    await send_typing(chat_id)

    # ── Step 6: Load preferences (keyed by shop_id, NOT session_id) ──────────
    preferences = await load_preferences_for_context()

    # ── Step 7: Process through agent ────────────────────────────────────────
    try:
        reply_text, file_paths = await get_agent().process_message(
            chat_id=chat_id,
            user_message=user_query,
            preferences=preferences,
        )
    except Exception as exc:
        logger.exception("Agent error for chat_id=%d: %s", chat_id, exc)
        await send_message(
            chat_id,
            "⚠️ Something went wrong. Please try again. If the issue persists, use /new to reset.",
        )
        return {"ok": True}

    # ── Step 8: Send reply ────────────────────────────────────────────────────
    if reply_text:
        await send_message(chat_id, reply_text)

    # Send any generated documents (PDF invoices, PPTX decks)
    for file_path in file_paths:
        path = Path(file_path)
        caption = f"📄 {path.name}"
        await send_document(chat_id, file_path, caption)
        logger.info("Sent document %s to chat_id=%d", path.name, chat_id)

    return {"ok": True}


# ── Webhook setup ─────────────────────────────────────────────────────────────

async def set_webhook() -> None:
    """Register the webhook URL with Telegram."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{TELEGRAM_BASE}/setWebhook",
            json={
                "url": f"{settings.webhook_url}/telegram/webhook",
                "secret_token": settings.telegram_webhook_secret,
                "allowed_updates": ["message", "edited_message"],
            },
        )
        data = resp.json()
        if data.get("ok"):
            logger.info("Webhook registered: %s", settings.webhook_url)
        else:
            logger.error("Webhook registration failed: %s", data)
