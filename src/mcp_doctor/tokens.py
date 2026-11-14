"""Estimate how many tokens tool definitions add to every model turn.

Uses ``tiktoken`` (o200k_base) when it is installed and its encoding is available, otherwise a
characters/4 heuristic. Either way the number is an estimate: each provider wraps tool
definitions in its own format, so treat it as a relative measure, not an exact bill.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

_counter: Callable[[str], int] | None = None
_method: str | None = None


def _init() -> None:
    global _counter, _method
    if _counter is not None:
        return
    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        _counter = lambda s: len(enc.encode(s))  # noqa: E731
        _method = "tiktoken o200k_base (approximate)"
    except Exception:  # not installed, or encoding download blocked
        _counter = lambda s: max(1, round(len(s) / 4))  # noqa: E731
        _method = "characters / 4 heuristic (approximate)"


def method() -> str:
    _init()
    assert _method is not None
    return _method


def tool_payload(tool: dict[str, Any]) -> str:
    """The part of a tool definition a client sends to the model."""
    keep = {k: tool[k] for k in ("name", "description", "inputSchema") if k in tool}
    return json.dumps(keep, separators=(",", ":"), ensure_ascii=False)


def count_tool_tokens(tool: dict[str, Any]) -> int:
    _init()
    assert _counter is not None
    return _counter(tool_payload(tool))
