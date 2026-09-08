"""
KiranaBot — Gemini Provider

Uses the Google Gen AI SDK (google-generativeai).
Converts the existing Anthropic-format TOOLS_SCHEMA into Gemini
FunctionDeclarations at startup — zero duplication of tool definitions.

Agentic loop mirrors the Claude provider:
  generate_content() → function_call parts → execute tools → repeat
  generate_content() → text part only → return final text
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings
from app.providers.base import AbstractProvider

settings = get_settings()
logger = logging.getLogger(__name__)


def _anthropic_schema_to_gemini(tools_schema: list[dict]) -> list[Any]:
    """
    Convert Anthropic-format tool schemas to Gemini FunctionDeclarations.

    Anthropic format:
        {"name": "...", "description": "...", "input_schema": {type, properties, required}}

    Gemini format:
        genai.protos.FunctionDeclaration(name, description, parameters)
    """
    try:
        import google.generativeai as genai
        import google.generativeai.protos as protos
    except ImportError:
        logger.error("google-generativeai is not installed. Run: pip install google-generativeai")
        return []

    declarations = []
    for tool in tools_schema:
        schema = tool.get("input_schema", {})
        properties = {}
        for prop_name, prop_def in schema.get("properties", {}).items():
            prop_type = prop_def.get("type", "string")
            type_map = {
                "string": protos.Type.STRING,
                "integer": protos.Type.INTEGER,
                "number": protos.Type.NUMBER,
                "boolean": protos.Type.BOOLEAN,
                "object": protos.Type.OBJECT,
                "array": protos.Type.ARRAY,
            }
            properties[prop_name] = protos.Schema(
                type=type_map.get(prop_type, protos.Type.STRING),
                description=prop_def.get("description", ""),
            )

        parameters = protos.Schema(
            type=protos.Type.OBJECT,
            properties=properties,
            required=schema.get("required", []),
        )

        declarations.append(
            protos.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=parameters,
            )
        )
    return declarations


class GeminiProvider(AbstractProvider):
    """
    Google Gemini backend.

    Session history is stored as a list of Gemini Content dicts
    (role: user/model, parts: [...]).
    """

    def __init__(self, tools_schema: list[dict], system_prompt_builder: Any) -> None:
        self._tools_schema = tools_schema
        self._build_system_prompt = system_prompt_builder
        self._sessions: dict[int, list[dict]] = {}
        self._model: Any = None  # Lazy init so import errors surface clearly

    def _get_model(self, system_prompt: str) -> Any:
        """Lazy-initialize Gemini model with current system prompt."""
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai>=0.8.0"
            ) from exc

        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to .env to use Gemini."
            )

        genai.configure(api_key=settings.gemini_api_key)
        gemini_tools = _anthropic_schema_to_gemini(self._tools_schema)

        return genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_prompt,
            tools=gemini_tools,
        )

    def reset_session(self, chat_id: int) -> None:
        self._sessions.pop(chat_id, None)
        logger.info("[Gemini] Session reset for chat_id=%d", chat_id)

    @staticmethod
    def _clean_history(history: list[Any], max_items: int = 40) -> list[Any]:
        """
        Ensure history has valid turns and starts on a clean user message.
        """
        if not history:
            return []
        trimmed = list(history[-max_items:])
        # Pop leading non-user or function-response turns
        while trimmed:
            first = trimmed[0]
            role = getattr(first, "role", None) or (first.get("role") if isinstance(first, dict) else None)
            parts = getattr(first, "parts", None) or (first.get("parts") if isinstance(first, dict) else [])
            has_func_resp = any(hasattr(p, "function_response") and p.function_response.name for p in parts)
            if role == "user" and not has_func_resp:
                break
            trimmed.pop(0)
        return trimmed

    async def process_message(
        self,
        chat_id: int,
        user_message: str,
        preferences: dict[str, Any],
    ) -> tuple[str, list[str]]:
        system_prompt = self._build_system_prompt(preferences)
        model = self._get_model(system_prompt)

        prior_history = self._clean_history(self._sessions.get(chat_id, []))
        chat = model.start_chat(history=prior_history)

        file_paths: list[str] = []
        final_text = ""
        current_input: Any = user_message

        try:
            while True:
                response = await _run_gemini_sync(chat, current_input)

                # Extract parts
                parts = []
                try:
                    parts = response.candidates[0].content.parts
                except (IndexError, AttributeError):
                    pass

                # Check for tool/function calls
                function_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call.name]

                if not function_calls:
                    # End of turn — collect final text
                    for part in parts:
                        if hasattr(part, "text") and part.text:
                            final_text += part.text
                    break

                # ── Execute all function calls ───────────────────────────────
                function_responses = []
                for part in function_calls:
                    fc = part.function_call
                    tool_name = fc.name
                    tool_input = dict(fc.args) if fc.args else {}

                    result = await self._execute_tool(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        call_id=f"gemini-{tool_name}",
                    )

                    if result.get("ok") and "data" in result:
                        fp = result["data"].get("file_path")
                        if fp:
                            file_paths.append(fp)

                    try:
                        from google.generativeai.protos import FunctionResponse, Part
                        resp_dict = result if isinstance(result, dict) else {"result": str(result)}
                        resp_kwargs: dict[str, Any] = {"name": tool_name, "response": resp_dict}
                        if hasattr(fc, "id") and fc.id:
                            resp_kwargs["id"] = fc.id
                        function_responses.append(
                            Part(function_response=FunctionResponse(**resp_kwargs))
                        )
                    except Exception:
                        function_responses.append({"function_response": {"name": tool_name, "response": result}})

                current_input = function_responses

            # Save clean history from chat session
            self._sessions[chat_id] = self._clean_history(list(chat.history))
            return final_text, file_paths

        except Exception:
            # If a turn fails, reset session to avoid leaving broken/mismatched turns
            self._sessions.pop(chat_id, None)
            raise


async def _run_gemini_sync(chat: Any, message: Any) -> Any:
    """
    Run synchronous Gemini send_message in a thread pool
    to avoid blocking the async event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, chat.send_message, message)
