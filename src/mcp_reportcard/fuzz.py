"""Safe fuzzing: send malformed and edge-case arguments and check the server fails gracefully.

Safety model:
  * By default only tools annotated ``readOnlyHint: true`` (and not ``destructiveHint: true``)
    are called. Everything else is skipped and listed in the report.
  * ``allow_unsafe=True`` fuzzes every tool. Only use it against a test instance.
"""

from __future__ import annotations

import re
from contextlib import AsyncExitStack
from typing import Any

import anyio
from mcp import Client, MCPError

from mcp_reportcard.connect import new_client
from mcp_reportcard.models import FuzzCase, FuzzOutcome

MAX_PROPS_PER_TOOL = 5
LONG_STRING = "A" * 10_000
TRICKY_UNICODE = "ñ漢字🙂‮\u0000'\";--<script>"

# Stack traces only. A plain file path in an error is usually helpful (a filesystem or git
# server should say which allowed directory a path falls outside of), so paths alone are not
# flagged. Testing against the official reference servers showed path matching was too noisy.
LEAK_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)"),                   # Python
    re.compile(r'File "[^"]+", line \d+, in '),                           # Python frame
    re.compile(r"\n\s+at [\w.<>$\[\] ]+ \((?:[A-Za-z]:)?[/\\][^)]*:\d+:\d+\)"),  # Node.js frame
    re.compile(r"\n\s+at (?:[A-Za-z]:)?[/\\][^\s)]*:\d+:\d+"),            # Node.js anonymous frame
    re.compile(r"\n\s+at [\w$.]+\([\w$]+\.(?:java|kt):\d+\)"),            # JVM frame
    re.compile(r"goroutine \d+ \[[\w ]+\]:"),                             # Go panic
    re.compile(r"thread '[^']+' panicked at "),                           # Rust panic
]


def is_safe_to_fuzz(tool: dict[str, Any]) -> bool:
    ann = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
    return ann.get("readOnlyHint") is True and ann.get("destructiveHint") is not True


def _types(prop: dict[str, Any]) -> list[str]:
    t = prop.get("type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def sample_value(prop: dict[str, Any]) -> Any:
    """A plausible valid value for a property schema."""
    if "const" in prop:
        return prop["const"]
    if isinstance(prop.get("enum"), list) and prop["enum"]:
        return prop["enum"][0]
    if "default" in prop:
        return prop["default"]
    for key in ("anyOf", "oneOf"):
        if isinstance(prop.get(key), list):
            for option in prop[key]:
                if isinstance(option, dict) and _types(option) != ["null"]:
                    return sample_value(option)
    t = (_types(prop) or ["string"])[0]
    if t == "integer":
        return int(prop.get("minimum", 1))
    if t == "number":
        return float(prop.get("minimum", 1))
    if t == "boolean":
        return False
    if t == "array":
        return []
    if t == "object":
        return {k: sample_value(v) for k, v in (prop.get("properties") or {}).items()
                if k in (prop.get("required") or []) and isinstance(v, dict)}
    if t == "null":
        return None
    fmt = prop.get("format")
    if fmt == "uri":
        return "https://example.com"
    if fmt == "email":
        return "test@example.com"
    if fmt == "date":
        return "2026-01-01"
    if fmt == "date-time":
        return "2026-01-01T00:00:00Z"
    return "test" if prop.get("minLength", 0) <= 4 else "t" * int(prop["minLength"])


def wrong_type_value(prop: dict[str, Any]) -> Any | None:
    """A value that clearly violates the property's type, or None if we can't tell."""
    ts = set(_types(prop))
    if not ts or len(ts) > 1:
        return None
    t = ts.pop()
    return {
        "integer": "not-a-number",
        "number": "not-a-number",
        "boolean": "maybe",
        "string": 12345,
        "array": "not-a-list",
        "object": "not-an-object",
    }.get(t)


def make_cases(tool: dict[str, Any]) -> list[FuzzCase]:
    name = str(tool.get("name"))
    schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
    props: dict[str, Any] = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = [r for r in (schema.get("required") or []) if r in props]
    baseline = {r: sample_value(props[r]) for r in required if isinstance(props[r], dict)}

    cases: list[FuzzCase] = []
    if required:
        cases.append(FuzzCase(name, "missing required arguments", {}, True))
    for key, prop in list(props.items())[:MAX_PROPS_PER_TOOL]:
        if not isinstance(prop, dict):
            continue
        bad = wrong_type_value(prop)
        if bad is not None:
            cases.append(FuzzCase(name, f"wrong type for `{key}`", {**baseline, key: bad}, True))
        enum = prop.get("enum")
        if isinstance(enum, list) and enum and all(isinstance(v, str) for v in enum):
            cases.append(FuzzCase(name, f"value outside enum for `{key}`",
                                  {**baseline, key: "__not_a_valid_option__"}, True))
        if _types(prop) == ["string"] and "enum" not in prop and "format" not in prop:
            if "maxLength" not in prop:
                cases.append(FuzzCase(name, f"10k-char string for `{key}`",
                                      {**baseline, key: LONG_STRING}, False))
            if "pattern" not in prop:
                cases.append(FuzzCase(name, f"tricky unicode for `{key}`",
                                      {**baseline, key: TRICKY_UNICODE}, False))
    return cases


def find_leak(text: str) -> str | None:
    for pat in LEAK_PATTERNS:
        m = pat.search(text)
        if m:
            snippet = m.group(0)
            return snippet if len(snippet) <= 80 else snippet[:77] + "..."
    return None


def _result_text(result: Any) -> str:
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def classify(case: FuzzCase, *, is_error: bool, text: str) -> FuzzOutcome:
    leak = find_leak(text)
    if leak:
        return FuzzOutcome(case, "leaked", f"`{leak}`")
    if case.expect_error and not is_error:
        return FuzzOutcome(case, "accepted", "returned success")
    if is_error:
        return FuzzOutcome(case, "rejected" if case.expect_error else "ok", text[:120])
    return FuzzOutcome(case, "ok")


async def run_fuzz(
    source: Any,
    tools: list[dict[str, Any]],
    *,
    allow_unsafe: bool = False,
    timeout: float = 10.0,
) -> tuple[list[FuzzOutcome], list[str]]:
    """Fuzz eligible tools. Returns (outcomes, names_of_skipped_tools)."""
    eligible = [t for t in tools if allow_unsafe or is_safe_to_fuzz(t)]
    skipped = [str(t.get("name")) for t in tools if t not in eligible]
    outcomes: list[FuzzOutcome] = []

    stack = AsyncExitStack()
    client: Client | None = None

    async def connect() -> Client:
        nonlocal stack
        await stack.aclose()
        stack = AsyncExitStack()
        return await stack.enter_async_context(new_client(source))

    try:
        client = await connect()
        for tool in eligible:
            for case in make_cases(tool):
                try:
                    with anyio.fail_after(timeout):
                        result = await client.call_tool(case.tool, case.arguments)
                    outcomes.append(classify(case, is_error=bool(result.is_error),
                                             text=_result_text(result)))
                except TimeoutError:
                    outcomes.append(FuzzOutcome(case, "timeout", f"no reply within {timeout:g}s"))
                    client = await connect()
                except MCPError as e:  # protocol-level error: a valid way to reject input
                    outcomes.append(classify(case, is_error=True, text=str(e)))
                except Exception as e:  # transport died or the server crashed
                    outcomes.append(FuzzOutcome(case, "crashed", f"{type(e).__name__}: {e}"[:160]))
                    client = await connect()
    finally:
        await stack.aclose()
    return outcomes, skipped
