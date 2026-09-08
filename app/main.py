"""
SupermarketBot — Application Entry Point

FastAPI app with lifespan management, health check, and Telegram webhook router.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import get_settings
from app.database import close_db
from app.telegram_bridge import router as telegram_router, set_webhook
from app.dashboard import router as dashboard_router

settings = get_settings()

logging.basicConfig(
    level=logging.INFO if settings.app_env == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("🏪 SupermarketBot starting up...")

    # Register Telegram webhook (skip in test mode or if placeholder URL)
    if settings.app_env != "test" and settings.webhook_url and "example.com" not in settings.webhook_url:
        try:
            await set_webhook()
        except Exception as exc:
            logger.warning("Could not register webhook: %s", exc)

    yield

    logger.info("SupermarketBot shutting down...")
    await close_db()


app = FastAPI(
    title="SupermarketBot",
    description="AI-Powered Supermarket Operations Agent & Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files for frontend assets
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register routes
app.include_router(dashboard_router)
app.include_router(telegram_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "SupermarketBot",
        "version": "1.0.0",
        "env": settings.app_env,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level="info",
    )
