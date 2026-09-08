"""
Supermarket Operations — Tool Response Contract

All tools return a uniform dict so the agent and hooks can pattern-match reliably.
  Success: {"ok": True, "data": {...}}
  Failure: {"ok": False, "error_code": "SNAKE_CASE", "message": "human readable"}
"""
from __future__ import annotations
from typing import Any


def ok(data: Any) -> dict:
    return {"ok": True, "data": data}


def err(error_code: str, message: str, **extra: Any) -> dict:
    return {"ok": False, "error_code": error_code, "message": message, **extra}
