"""
KiranaBot — Application Configuration
All settings are loaded from environment variables (via .env file).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    # ── Anthropic / Claude ────────────────────────────────────────────────────
    anthropic_api_key: str = Field(...)
    claude_model: str = "claude-3-5-sonnet-20241022"

    # ── Google / Gemini ───────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"

    # ── Provider fallback ─────────────────────────────────────────────────────
    ai_fallback_enabled: bool = True

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = Field(...)
    telegram_webhook_secret: str = Field(...)
    webhook_url: str = Field(...)

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(...)
    database_url_sync: str = Field(...)

    # ── Shop defaults (single-shop deployment) ────────────────────────────────
    shop_id: str = "00000000-0000-0000-0000-000000000001"
    shop_name: str = "Metro Supermarket"
    shop_owner_name: str = "Store Manager"
    shop_gstin: str = ""
    shop_address: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"

    # ── Documents ─────────────────────────────────────────────────────────────
    docs_output_dir: str = "docs_output"


@lru_cache
def get_settings() -> Settings:
    return Settings()
