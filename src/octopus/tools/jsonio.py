from __future__ import annotations

import json
from typing import Any


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return value


def success(tool: str, result: Any) -> dict[str, Any]:
    return {"ok": True, "tool": tool, "result": to_jsonable(result)}


def failure(tool: str, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


def dumps(payload: Any) -> str:
    return json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2) + "\n"
