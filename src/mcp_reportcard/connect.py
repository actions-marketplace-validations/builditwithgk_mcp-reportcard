"""Connect to a live MCP server and fetch its tool list. Requires the ``mcp`` SDK."""

from __future__ import annotations

import os
import shlex
import sys
from typing import Any, TextIO

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

# Where a stdio server's own stderr goes. Silenced by default so the report stays readable;
# the CLI's --server-logs flag points it at the terminal.
_server_errlog: TextIO | None = None


def show_server_logs(enabled: bool) -> None:
    global _server_errlog
    _server_errlog = sys.stderr if enabled else None


def _devnull() -> TextIO:
    return open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115  lives as long as the process


def parse_source(source: Any) -> Any:
    """Turn a CLI source into a URL, StdioServerParameters, or a pass-through object.

    * ``http://`` / ``https://`` URL -> Streamable HTTP
    * any other string -> a command line, launched over stdio
    * anything else (e.g. an in-process ``MCPServer``) is passed through unchanged
    """
    if not isinstance(source, str):
        return source
    if source.startswith(("http://", "https://")):
        return source
    parts = shlex.split(source, posix=os.name != "nt")
    if os.name == "nt":  # shlex(posix=False) keeps the quotes; strip them
        parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    if not parts:
        raise ValueError("Empty server command.")
    return StdioServerParameters(command=parts[0], args=parts[1:])


def new_client(source: Any) -> Client:
    """A fresh, unopened Client for ``source``. Each call can be entered once."""
    target = parse_source(source)
    if isinstance(target, StdioServerParameters):
        return Client(stdio_client(target, errlog=_server_errlog or _devnull()))
    return Client(target)


def tool_to_dict(tool: Any) -> dict[str, Any]:
    return tool.model_dump(by_alias=True, exclude_none=True, mode="json")


async def fetch_tools(source: Any) -> tuple[str, list[dict[str, Any]]]:
    """Return (server_name, tools) for a live server, following pagination."""
    async with new_client(source) as client:
        name = client.server_info.name if client.server_info else str(source)
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(100):  # hard stop on a server that paginates forever
            result = await client.list_tools(cursor=cursor)
            tools.extend(tool_to_dict(t) for t in result.tools)
            cursor = result.next_cursor
            if not cursor:
                break
        return name, tools
