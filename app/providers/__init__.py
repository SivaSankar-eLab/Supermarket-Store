"""
KiranaBot — Provider Factory

get_provider(name) → singleton AbstractProvider instance.

Fallback logic (when AI_FALLBACK_ENABLED=true):
  If GeminiProvider raises during process_message, transparently retries
  on ClaudeProvider for that single message.
  This fires ONLY on exceptions (network, quota, bad auth) — never on
  normal tool-use flow — so there is zero risk of double tool execution.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.providers.base import AbstractProvider

settings = get_settings()
logger = logging.getLogger(__name__)

# Singleton registry
_providers: dict[str, AbstractProvider] = {}


def _make_provider(name: str, tools_schema: list[dict], system_prompt_builder: Any) -> AbstractProvider:
    if name == "claude":
        from app.providers.claude import ClaudeProvider
        return ClaudeProvider(tools_schema, system_prompt_builder)
    elif name == "gemini":
        from app.providers.gemini import GeminiProvider
        return GeminiProvider(tools_schema, system_prompt_builder)
    else:
        raise ValueError(f"Unknown provider: '{name}'. Valid values: claude, gemini")


def init_providers(tools_schema: list[dict], system_prompt_builder: Any, tool_functions: dict[str, Any]) -> None:
    """
    Called once at startup from agent.py to inject shared state into providers.
    Both providers share the same TOOL_FUNCTIONS registry — single source of truth.
    """
    AbstractProvider.TOOL_FUNCTIONS = tool_functions
    _providers["claude"] = _make_provider("claude", tools_schema, system_prompt_builder)
    _providers["gemini"] = _make_provider("gemini", tools_schema, system_prompt_builder)
    logger.info("Providers initialized: %s", list(_providers.keys()))


def get_provider(name: str) -> AbstractProvider:
    """Return the singleton provider by name. Defaults to claude."""
    name = (name or "claude").strip().lower()
    if name not in _providers:
        logger.warning("Unknown provider '%s', falling back to claude", name)
        name = "claude"
    return _providers[name]


def reset_all_sessions(chat_id: int) -> None:
    """Reset session history for all providers (called on /new)."""
    for provider in _providers.values():
        provider.reset_session(chat_id)


async def process_with_fallback(
    provider_name: str,
    chat_id: int,
    user_message: str,
    preferences: dict[str, Any],
) -> tuple[str, list[str]]:
    """
    Run process_message on the requested provider.
    If it raises AND ai_fallback_enabled=True AND the primary is not already claude,
    retry once on ClaudeProvider and log a warning.

    The fallback only triggers on exceptions — not on successful tool-use responses.
    This guarantees no double tool execution.
    """
    primary = get_provider(provider_name)
    try:
        return await primary.process_message(chat_id, user_message, preferences)
    except Exception as exc:
        if settings.ai_fallback_enabled and provider_name != "claude":
            logger.warning(
                "[Fallback] %s provider failed (%s). Retrying on Claude.",
                provider_name, exc,
            )
            claude = get_provider("claude")
            return await claude.process_message(chat_id, user_message, preferences)
        raise
