"""
KiranaBot — Claude Provider

Extracted from the original agent.py with zero logic changes.
Uses the Anthropic SDK and the Anthropic-format TOOLS_SCHEMA.
"""
from __future__ import annotations

import logging
from typing import Any

import anthropic

from app.config import get_settings
from app.providers.base import AbstractProvider

settings = get_settings()
logger = logging.getLogger(__name__)


class ClaudeProvider(AbstractProvider):
    """
    Anthropic Claude backend.

    Agentic loop:
      POST messages → stop_reason == "tool_use" → execute tools → repeat
      POST messages → stop_reason == "end_turn"  → return final text
    """

    def __init__(self, tools_schema: list[dict], system_prompt_builder: Any) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._tools_schema = tools_schema
        self._build_system_prompt = system_prompt_builder
        # In-memory session history: chat_id → list[dict]
        self._sessions: dict[int, list[dict]] = {}

    def reset_session(self, chat_id: int) -> None:
        self._sessions.pop(chat_id, None)
        logger.info("[Claude] Session reset for chat_id=%d", chat_id)

    async def process_message(
        self,
        chat_id: int,
        user_message: str,
        preferences: dict[str, Any],
    ) -> tuple[str, list[str]]:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = []

        messages = self._sessions[chat_id]
        messages.append({"role": "user", "content": user_message})
        system_prompt = self._build_system_prompt(preferences)

        file_paths: list[str] = []
        final_text = ""

        # ── Agentic loop ──────────────────────────────────────────────────────
        while True:
            response = self._client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system_prompt,
                tools=self._tools_schema,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text = block.text
                break

            if response.stop_reason != "tool_use":
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text = block.text
                break

            # ── Execute tool calls ────────────────────────────────────────────
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                result = await self._execute_tool(
                    tool_name=block.name,
                    tool_input=block.input,
                    call_id=block.id,
                )

                if result.get("ok") and "data" in result:
                    fp = result["data"].get("file_path")
                    if fp:
                        file_paths.append(fp)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

            messages.append({"role": "user", "content": tool_results})

        # Trim to last 40 messages to stay within context limits
        self._sessions[chat_id] = messages[-40:]
        return final_text, file_paths
