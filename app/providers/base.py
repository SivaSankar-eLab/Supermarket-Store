"""
KiranaBot — AbstractProvider Base Class

Every LLM provider (Claude, Gemini, …) must subclass AbstractProvider.
The shared _execute_tool coroutine is defined here so business-rule hooks
and tool dispatch happen exactly once, regardless of which model is active.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.hooks import pre_tool_use_hook, post_tool_use_hook, pre_tool_timing

logger = logging.getLogger(__name__)


class AbstractProvider(ABC):
    """
    Common interface for all AI provider backends.

    Subclasses own:
      - their SDK client
      - session history format
      - the agentic loop (how tool calls are parsed from model responses)

    Subclasses must NOT re-implement tool dispatch or hook logic —
    use _execute_tool() from this base class.
    """

    # Subclasses register the shared tool function registry here.
    # Set by agent.py after both modules are loaded.
    TOOL_FUNCTIONS: dict[str, Any] = {}

    @abstractmethod
    async def process_message(
        self,
        chat_id: int,
        user_message: str,
        preferences: dict[str, Any],
    ) -> tuple[str, list[str]]:
        """
        Process one user message through the provider's agentic loop.

        Returns:
            (reply_text, file_paths) — file_paths for generated PDFs/PPTX
        """

    @abstractmethod
    def reset_session(self, chat_id: int) -> None:
        """Clear in-memory conversation history for this chat."""

    # ── Shared tool execution ─────────────────────────────────────────────────

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        call_id: str = "",
    ) -> dict[str, Any]:
        """
        Run pre-hook → tool function → post-hook.

        This is the single place tool calls are dispatched.
        Both ClaudeProvider and GeminiProvider call this method,
        guaranteeing identical business-rule enforcement.

        Returns the tool result dict.
        """
        pre_tool_timing(tool_name, call_id)

        # ── Pre-hook (independent guardrail layer) ────────────────────────────
        hook_result = await pre_tool_use_hook(tool_name, tool_input)
        if hook_result and hook_result.get("block"):
            result = hook_result["result"]
            logger.warning(
                "Hook blocked %s: %s", tool_name, result.get("error_code")
            )
        else:
            # ── Dispatch to tool function ─────────────────────────────────────
            tool_fn = self.TOOL_FUNCTIONS.get(tool_name)
            if tool_fn is None:
                result = {
                    "ok": False,
                    "error_code": "UNKNOWN_TOOL",
                    "message": f"Tool '{tool_name}' is not registered.",
                }
            else:
                try:
                    result = await tool_fn(**tool_input)
                except Exception as exc:
                    logger.exception("Tool %s raised: %s", tool_name, exc)
                    result = {
                        "ok": False,
                        "error_code": "TOOL_ERROR",
                        "message": f"Internal error in {tool_name}: {exc}",
                    }

        # ── Post-hook (logging + metrics) ─────────────────────────────────────
        await post_tool_use_hook(tool_name, tool_input, result, call_id)

        return result
