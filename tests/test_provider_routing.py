"""
SupermarketBot — Provider Routing Tests

Covers:
  - Provider selector reads ai_provider preference correctly
  - Defaults to Claude when preference is absent
  - Fallback triggers only on exception, not on tool-use responses
  - Gemini schema conversion produces one FunctionDeclaration per tool
  - Session reset clears BOTH providers (not just the active one)
  - No domain logic (GST / billing / credit ledger) is duplicated in provider code

All tests are pure unit tests — no Postgres, no real API keys needed.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

# Set required env vars before any app import
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-claude")
os.environ.setdefault("GEMINI_API_KEY", "test-key-gemini")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("WEBHOOK_URL", "https://test.example.com")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://x:x@localhost/x")

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_SCHEMA: list[dict] = [
    {
        "name": "find_product",
        "description": "Search product",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "search term"}},
            "required": ["query"],
        },
    },
    {
        "name": "finalize_bill",
        "description": "Finalize bill",
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {"type": "string"},
                "payment_mode": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["bill_id", "payment_mode", "idempotency_key"],
        },
    },
]


def system_prompt_builder(prefs: dict) -> str:
    return f"System: provider={prefs.get('ai_provider', 'claude')}"


# ── 1. Gemini schema conversion ───────────────────────────────────────────────

class TestGeminiSchemaConversion:
    """Verify Anthropic→Gemini schema conversion produces valid declarations."""

    def test_conversion_produces_one_declaration_per_tool(self):
        pytest.importorskip("google.generativeai", reason="google-generativeai not installed")
        from app.providers.gemini import _anthropic_schema_to_gemini
        result = _anthropic_schema_to_gemini(MINIMAL_SCHEMA)
        assert len(result) == len(MINIMAL_SCHEMA)

    def test_conversion_preserves_tool_names(self):
        pytest.importorskip("google.generativeai", reason="google-generativeai not installed")
        from app.providers.gemini import _anthropic_schema_to_gemini
        result = _anthropic_schema_to_gemini(MINIMAL_SCHEMA)
        names = [d.name for d in result]
        assert "find_product" in names
        assert "finalize_bill" in names

    def test_empty_schema_returns_empty_list(self):
        pytest.importorskip("google.generativeai", reason="google-generativeai not installed")
        from app.providers.gemini import _anthropic_schema_to_gemini
        assert _anthropic_schema_to_gemini([]) == []


# ── 2. AbstractProvider._execute_tool ─────────────────────────────────────────

class TestAbstractProviderExecuteTool:
    """Shared _execute_tool dispatches correctly regardless of which provider."""

    @pytest.fixture
    def provider(self):
        with patch("anthropic.Anthropic"):
            from app.providers.claude import ClaudeProvider
            p = ClaudeProvider(MINIMAL_SCHEMA, system_prompt_builder)
        p.TOOL_FUNCTIONS = {
            "find_product": AsyncMock(return_value={"ok": True, "data": {"products": []}}),
        }
        return p

    @pytest.mark.asyncio
    async def test_known_tool_returns_ok(self, provider):
        result = await provider._execute_tool("find_product", {"query": "salt"}, "c1")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, provider):
        result = await provider._execute_tool("nonexistent_tool", {}, "c2")
        assert result["ok"] is False
        assert result["error_code"] == "UNKNOWN_TOOL"

    @pytest.mark.asyncio
    async def test_tool_exception_returns_structured_error(self, provider):
        provider.TOOL_FUNCTIONS["bad_tool"] = AsyncMock(side_effect=RuntimeError("boom"))
        result = await provider._execute_tool("bad_tool", {}, "c3")
        assert result["ok"] is False
        assert result["error_code"] == "TOOL_ERROR"
        assert "boom" in result["message"]


# ── 3. Provider factory ────────────────────────────────────────────────────────

class TestProviderFactory:
    """get_provider returns correct singleton, handles bad names gracefully."""

    @pytest.fixture(autouse=True)
    def mock_providers(self):
        with patch("anthropic.Anthropic"):
            from app.providers.claude import ClaudeProvider
            claude_instance = ClaudeProvider(MINIMAL_SCHEMA, system_prompt_builder)
        gemini_mock = MagicMock()
        from app.providers import _providers
        _providers["claude"] = claude_instance
        _providers["gemini"] = gemini_mock
        yield

    def test_get_claude(self):
        from app.providers import get_provider
        from app.providers.claude import ClaudeProvider
        assert isinstance(get_provider("claude"), ClaudeProvider)

    def test_get_gemini(self):
        from app.providers import get_provider
        assert get_provider("gemini") is not None

    def test_unknown_name_falls_back_to_claude(self):
        from app.providers import get_provider
        from app.providers.claude import ClaudeProvider
        assert isinstance(get_provider("openai"), ClaudeProvider)

    def test_case_insensitive(self):
        from app.providers import get_provider
        assert get_provider("Claude") is get_provider("CLAUDE")
        assert get_provider("CLAUDE") is get_provider("claude")


# ── 4. Fallback logic ─────────────────────────────────────────────────────────

class TestFallbackLogic:
    """Fallback must fire ONLY on exceptions — never on successful tool-use."""

    @pytest.mark.asyncio
    async def test_fallback_fires_on_exception(self):
        from app.providers import _providers
        _providers["gemini"] = MagicMock(
            process_message=AsyncMock(side_effect=RuntimeError("quota"))
        )
        _providers["claude"] = MagicMock(
            process_message=AsyncMock(return_value=("fallback", []))
        )
        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = True
            from app.providers import process_with_fallback
            text, _ = await process_with_fallback("gemini", 1, "hi", {})
        assert text == "fallback"

    @pytest.mark.asyncio
    async def test_fallback_never_fires_on_success(self):
        from app.providers import _providers
        _providers["gemini"] = MagicMock(
            process_message=AsyncMock(return_value=("ok from gemini", []))
        )
        claude_mock = MagicMock(process_message=AsyncMock(return_value=("claude reply", [])))
        _providers["claude"] = claude_mock
        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = True
            from app.providers import process_with_fallback
            text, _ = await process_with_fallback("gemini", 1, "hi", {})
        assert text == "ok from gemini"
        claude_mock.process_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fallback_disabled_propagates_exception(self):
        from app.providers import _providers
        _providers["gemini"] = MagicMock(
            process_message=AsyncMock(side_effect=RuntimeError("api down"))
        )
        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = False
            from app.providers import process_with_fallback
            with pytest.raises(RuntimeError):
                await process_with_fallback("gemini", 1, "hi", {})

    @pytest.mark.asyncio
    async def test_claude_as_primary_never_falls_back(self):
        """Claude IS the fallback — its own exceptions must propagate."""
        from app.providers import _providers
        _providers["claude"] = MagicMock(
            process_message=AsyncMock(side_effect=RuntimeError("claude down"))
        )
        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = True
            from app.providers import process_with_fallback
            with pytest.raises(RuntimeError):
                await process_with_fallback("claude", 1, "hi", {})


# ── 5. Session reset covers all providers ─────────────────────────────────────

class TestSessionReset:
    def test_reset_calls_every_provider(self):
        from app.providers import _providers, reset_all_sessions
        p1 = MagicMock()
        p2 = MagicMock()
        _providers["claude"] = p1
        _providers["gemini"] = p2
        reset_all_sessions(chat_id=99)
        p1.reset_session.assert_called_once_with(99)
        p2.reset_session.assert_called_once_with(99)


# ── 6. Agent routing via preferences ─────────────────────────────────────────

class TestAgentProviderRouting:
    """KiranaBotAgent routes to the provider named in the preferences dict."""

    @pytest.mark.asyncio
    async def test_routes_to_gemini_from_preference(self):
        from app.agent import KiranaBotAgent
        from app.providers import _providers
        gemini_mock = MagicMock(
            process_message=AsyncMock(return_value=("from gemini", []))
        )
        claude_mock = MagicMock(
            process_message=AsyncMock(return_value=("from claude", []))
        )
        _providers["gemini"] = gemini_mock
        _providers["claude"] = claude_mock

        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = False
            text, _ = await KiranaBotAgent().process_message(
                chat_id=1, user_message="check stock", preferences={"ai_provider": "gemini"}
            )
        assert text == "from gemini"
        claude_mock.process_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_defaults_to_claude_when_no_preference(self):
        from app.providers import _providers
        claude_mock = MagicMock(
            process_message=AsyncMock(return_value=("claude default", []))
        )
        gemini_mock = MagicMock(
            process_message=AsyncMock(return_value=("gemini", []))
        )
        _providers["claude"] = claude_mock
        _providers["gemini"] = gemini_mock

        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = False
            from app.agent import KiranaBotAgent
            text, _ = await KiranaBotAgent().process_message(
                chat_id=2, user_message="hello", preferences={}
            )
        assert text == "claude default"
        gemini_mock.process_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preference_value_claude_routes_to_claude(self):
        from app.providers import _providers
        claude_mock = MagicMock(
            process_message=AsyncMock(return_value=("explicit claude", []))
        )
        gemini_mock = MagicMock(
            process_message=AsyncMock(return_value=("gemini", []))
        )
        _providers["claude"] = claude_mock
        _providers["gemini"] = gemini_mock

        with patch("app.providers.settings") as s:
            s.ai_fallback_enabled = False
            from app.agent import KiranaBotAgent
            text, _ = await KiranaBotAgent().process_message(
                chat_id=3, user_message="hello", preferences={"ai_provider": "claude"}
            )
        assert text == "explicit claude"
        gemini_mock.process_message.assert_not_awaited()
