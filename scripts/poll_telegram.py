"""
KiranaBot — Telegram Long Polling Script
Use this for local development without ngrok/webhooks.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
import httpx

from app.config import get_settings
from app.database import close_db
from app.telegram_bridge import (
    ensure_shop_exists,
    is_duplicate_update,
    send_message,
    send_document,
    send_typing,
    download_telegram_file,
)
from app.agent import get_agent
from app.tools.preferences import load_preferences_for_context

settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("telegram_polling")

TELEGRAM_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def delete_webhook():
    """Clear any registered webhook so Telegram long polling works."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{TELEGRAM_BASE}/deleteWebhook", params={"drop_pending_updates": False})
        logger.info("Cleared Telegram webhook: %s", resp.json())


async def poll():
    await delete_webhook()
    offset = 0
    logger.info("🤖 KiranaBot Telegram Long Poller STARTED!")
    logger.info("Send a message to your bot on Telegram now.")

    async with httpx.AsyncClient(timeout=45) as client:
        while True:
            try:
                resp = await client.get(
                    f"{TELEGRAM_BASE}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                if resp.status_code != 200:
                    logger.warning("getUpdates status %d: %s", resp.status_code, resp.text)
                    await asyncio.sleep(2)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    logger.warning("getUpdates error: %s", data)
                    await asyncio.sleep(2)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    update_id = update["update_id"]
                    message = update.get("message") or update.get("edited_message") or {}
                    if not message:
                        continue

                    chat_id = message.get("chat", {}).get("id", 0)
                    text = (message.get("text") or "").strip()
                    caption = (message.get("caption") or "").strip()
                    photo = message.get("photo")
                    document = message.get("document")
                    voice = message.get("voice") or message.get("audio")

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
                            continue
                    elif voice:
                        file_id = voice["file_id"]
                        try:
                            downloaded_path = await download_telegram_file(file_id)
                            image_prompt = f"[User sent voice-note order: audio_file='{downloaded_path.as_posix()}'] Transcribe this customer voice order, find the matching products in the catalog, start a draft bill, and add the requested items."
                        except Exception as v_err:
                            logger.error("Failed to download Telegram voice note: %s", v_err)
                            await send_message(chat_id, "⚠️ Failed to download voice note. Please try again.")
                            continue
                    elif document and str(document.get("mime_type", "")).startswith("image/"):
                        file_id = document["file_id"]
                        try:
                            downloaded_path = await download_telegram_file(file_id)
                            hint = caption if caption else "Identify this product or barcode, check catalog stock, and suggest next actions."
                            image_prompt = f"[User sent product photo: image_path='{downloaded_path.as_posix()}'] {hint}"
                        except Exception as dl_err:
                            logger.error("Failed to download Telegram image doc: %s", dl_err)
                            await send_message(chat_id, "⚠️ Failed to download document image. Please try again.")
                            continue

                    user_query = image_prompt if image_prompt else (text or caption)
                    if not chat_id or not user_query:
                        continue

                    if await is_duplicate_update(update_id, chat_id):
                        logger.info("Skipping duplicate update_id=%d", update_id)
                        continue

                    await ensure_shop_exists(chat_id)

                    # Handlers
                    if user_query.lower() in {"/new", "/start"}:
                        get_agent().reset_session(chat_id)
                        await send_message(
                            chat_id,
                            "🔄 *New session started!*\n\n"
                            "Your shop preferences are still remembered.\n"
                            "How can I help you today?",
                        )
                        continue

                    if user_query.lower() == "/help":
                        await send_message(
                            chat_id,
                            "🏪 *Supermarket Bot Commands*\n\n"
                            "📦 *Inventory*\n"
                            "• 'What's the stock of wheat flour?'\n"
                            "• 'Add 50kg Aashirvaad flour at ₹42, sell at ₹50'\n\n"
                            "🧾 *Billing*\n"
                            "• 'New bill for Ravi: 2kg flour'\n"
                            "• 'Finalize bill via UPI'\n\n"
                            "📒 *Customer Credit (Ledger)*\n"
                            "• 'Ravi took ₹500 on credit'\n"
                            "• 'Ravi paid ₹200'\n\n"
                            "⚙️ *Settings*\n"
                            "• 'AI Gemini' — switch to Gemini\n"
                            "• 'AI Claude' — switch to Claude\n\n"
                            "/new — Start fresh session\n"
                            "/help — Show this message",
                        )
                        continue

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
                        continue

                    await send_typing(chat_id)
                    preferences = await load_preferences_for_context()

                    try:
                        reply_text, file_paths = await get_agent().process_message(
                            chat_id=chat_id,
                            user_message=user_query,
                            preferences=preferences,
                        )
                        if reply_text:
                            await send_message(chat_id, reply_text)
                        for file_path in file_paths:
                            await send_document(chat_id, file_path, f"📄 {Path(file_path).name}")
                    except Exception as exc:
                        logger.exception("Error processing message: %s", exc)
                        await send_message(chat_id, "⚠️ Error processing message. Try again or /new.")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Polling loop error: %s", e)
                await asyncio.sleep(2)

    await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(poll())
    except KeyboardInterrupt:
        logger.info("Polling stopped by user.")
