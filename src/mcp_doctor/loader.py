"""Load tool definitions from a saved ``tools/list`` result.

Accepted shapes:
  * a full JSON-RPC response: ``{"jsonrpc": "2.0", "result": {"tools": [...]}}``
  * a ``tools/list`` result: ``{"tools": [...]}``
  * a bare list of tools: ``[{...}, {...}]``

Tools are kept as plain dicts in MCP wire format (camelCase keys such as ``inputSchema``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LoadError(ValueError):
    pass


def load_tools(data: Any) -> list[dict[str, Any]]:
    """Normalise parsed JSON into a list of tool dicts."""
    if isinstance(data, dict) and "result" in data and isinstance(data["result"], dict):
        data = data["result"]
    if isinstance(data, dict) and "tools" in data:
        data = data["tools"]
    if not isinstance(data, list):
        raise LoadError(
            'Expected a list of tools, {"tools": [...]}, or a JSON-RPC tools/list response.'
        )
    tools: list[dict[str, Any]] = []
    for i, t in enumerate(data):
        if not isinstance(t, dict):
            raise LoadError(f"Tool #{i + 1} is not a JSON object.")
        tools.append(t)
    return tools


def load_tools_text(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise LoadError(f"Invalid JSON: {e.msg} (line {e.lineno}, column {e.colno}).") from e
    return load_tools(data)


def load_tools_file(path: str | Path) -> list[dict[str, Any]]:
    return load_tools_text(Path(path).read_text(encoding="utf-8"))
