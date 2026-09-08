"""
KiranaBot — Scheduled Weekly Analysis Deck Auto-Sender

Run this standalone or via cron/scheduler every Monday morning at 8:00 AM.
It generates the executive store analysis PowerPoint deck and dispatches it
directly to the registered store owner on Telegram.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.database import close_db
from app.telegram_bridge import send_message, send_document
from app.tools.documents import generate_analysis_deck

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("weekly_scheduler")
settings = get_settings()


async def run_weekly_report(chat_id: int | None = None):
    """Generate and send the weekly store analysis deck."""
    logger.info("📊 Starting scheduled weekly analysis deck generation...")
    
    result = await generate_analysis_deck(period="week")
    if not result.get("ok"):
        logger.error("Failed to generate weekly analysis deck: %s", result)
        return

    deck_path = result["data"]["file_path"]
    filename = result["data"]["filename"]
    logger.info("✅ Weekly PPTX deck generated at: %s", deck_path)

    target_chat = chat_id or getattr(settings, "admin_chat_id", None)
    if target_chat:
        await send_message(
            target_chat,
            "📈 *Weekly Executive Performance Deck*\n\n"
            "Good morning! Here is your automated store performance analysis deck for the past week, "
            "including sales breakdown, top SKUs, stock health, and GST tax collections.",
        )
        await send_document(target_chat, deck_path, f"📊 {filename}")
        logger.info("Dispatched weekly deck to Telegram chat_id=%s", target_chat)
    else:
        logger.info("Saved weekly deck locally: %s (No chat_id specified)", deck_path)

    await close_db()


if __name__ == "__main__":
    asyncio.run(run_weekly_report())
