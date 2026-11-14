"""Static lint rules for MCP tool definitions. No network, no LLM, no tool calls.

Each rule has a stable ID so reports, docs and CI configs can refer to it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from mcp_reportcard.models import Issue, Severity

E, W, I = Severity.ERROR, Severity.WARNING, Severity.INFO

# Rule catalogue: id -> (severity, short title). Used for docs and `mcp-reportcard rules`.
RULES: dict[str, tuple[Severity, str]] = {
    "N001": (E, "Tool has no name"),
    "N002": (E, "Duplicate tool name"),
    "N003": (E, "Tool name uses characters outside A-Z a-z 0-9 _ - ."),
    "N004": (I, "Mixed naming styles across tools"),
    "N005": (W, "Tool name longer than 64 characters"),
    "D001": (E, "Tool has no description"),
    "D002": (W, "Description too short to guide a model"),
    "D003": (I, "Description very long"),
    "D004": (W, "Description only restates the tool name"),
    "D005": (I, "Similar tool exists, but no 'when to use' guidance"),
    "S001": (E, "inputSchema missing or not an object schema"),
    "S002": (W, "Parameter has no type"),
    "S003": (W, "Parameter has no description"),
    "S004": (E, "required lists a parameter that does not exist"),
    "S005": (I, "Free-form object parameter"),
    "S006": (I, "Schema nested too deeply"),
    "S007": (I, "Parameter looks like a fixed set of values but has no enum"),
    "S008": (I, "Too many parameters"),
    "A001": (W, "No safety annotations (readOnlyHint / destructiveHint)"),
    "A002": (W, "Contradictory annotations"),
    "T001": (I, "Tool definition is heavy on tokens"),
    "X001": (W, "Two tools have overlapping descriptions"),
    "X002": (W, "Tool list is heavy on tokens for every turn"),
    "X003": (W, "Too many tools for reliable selection"),
    "X004": (E, "Server exposes no tools"),
    "F001": (W, "Accepted input that violates its own schema"),
    "F002": (E, "Error output leaks internals (stack trace or file paths)"),
    "F003": (E, "Crashed or timed out on bad input"),
}

NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")
WORD_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "by", "with", "from", "this",
    "that", "is", "are", "be", "it", "its", "as", "at", "tool", "tools", "given", "specified",
}
USAGE_CUES = {"use", "when", "call", "prefer", "instead", "only", "before", "after", "if", "useful"}
ENUM_HINT_NAMES = {
    "mode", "type", "kind", "format", "sort", "sort_by", "sortby", "order", "order_by", "level",
    "status", "unit", "units", "method", "direction", "category", "priority", "severity",
}
TYPE_KEYS = ("type", "enum", "const", "anyOf", "oneOf", "allOf", "$ref", "not")

MIN_DESC_CHARS = 20
MAX_DESC_CHARS = 1024
MAX_NAME_CHARS = 64
MAX_DEPTH = 3
MAX_PARAMS = 10
HEAVY_TOOL_TOKENS = 800
HEAVY_SERVER_TOKENS = 10_000
MAX_TOOLS = 40
OVERLAP_THRESHOLD = 0.6
SIMILAR_THRESHOLD = 0.35  # close enough that "when to use" guidance matters


def _issue(rule: str, message: str, fix: str, tool: str | None) -> Issue:
    return Issue(rule=rule, severity=RULES[rule][0], message=message, fix=fix, tool=tool)


def words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def name_words(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return words(spaced.replace("_", " ").replace("-", " ").replace(".", " "))


def content_words(text: str) -> set[str]:
    return {w for w in words(text) if w not in STOPWORDS and len(w) > 1}


def name_style(name: str) -> str:
    if "-" in name:
        return "kebab-case"
    if "." in name:
        return "dot.case"
    if "_" in name or name.islower():
        return "snake_case"
    if name[:1].islower() and any(c.isupper() for c in name):
        return "camelCase"
    if name[:1].isupper():
        return "PascalCase"
    return "other"


def _has_type(prop: Any) -> bool:
    return isinstance(prop, dict) and any(k in prop for k in TYPE_KEYS)


def _types(prop: dict[str, Any]) -> set[str]:
    t = prop.get("type")
    if isinstance(t, str):
        return {t}
    if isinstance(t, list):
        return {x for x in t if isinstance(x, str)}
    return set()


def walk_properties(
    schema: dict[str, Any], path: str = "", depth: int = 1
) -> Iterator[tuple[str, dict[str, Any], int]]:
    """Yield (dotted_path, property_schema, depth) for every named property, recursively."""
    props = schema.get("properties")
    if not isinstance(props, dict):
        return
    for key, prop in props.items():
        p = f"{path}.{key}" if path else key
        if not isinstance(prop, dict):
            yield p, {}, depth
            continue
        yield p, prop, depth
        if "properties" in prop:
            yield from walk_properties(prop, p, depth + 1)
        items = prop.get("items")
        if isinstance(items, dict) and "properties" in items:
            yield from walk_properties(items, f"{p}[]", depth + 1)


def lint_tool(tool: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    name = tool.get("name")
    label = name if isinstance(name, str) and name else None

    # Names
    if not label:
        issues.append(_issue("N001", "Tool has no name.", "Give every tool a unique `name`.", None))
    else:
        if not NAME_RE.match(label):
            issues.append(_issue(
                "N003", f"Name `{label}` contains characters many clients reject.",
                "Use only letters, digits, `_`, `-` and `.` (1-128 chars), e.g. `search_orders`.",
                label))
        if len(label) > MAX_NAME_CHARS:
            issues.append(_issue(
                "N005", f"Name is {len(label)} characters; some clients cap tool names at 64.",
                "Shorten the name to 64 characters or fewer.", label))

    # Description
    desc = tool.get("description")
    desc = desc.strip() if isinstance(desc, str) else ""
    if not desc:
        issues.append(_issue(
            "D001", "No description, so the model has only the name to guess from.",
            "Describe what the tool does, what it returns, and when to use it.", label))
    else:
        if len(desc) < MIN_DESC_CHARS:
            issues.append(_issue(
                "D002", f'Description "{desc}" is only {len(desc)} characters.',
                "Expand to 1-3 sentences: what it does, what it returns, when to pick it.", label))
        if len(desc) > MAX_DESC_CHARS:
            issues.append(_issue(
                "D003", f"Description is {len(desc)} characters, which costs tokens on every turn.",
                "Move long reference material into a resource or parameter descriptions.", label))
        dw, nw = content_words(desc), set(name_words(label or ""))
        if dw and nw and dw <= nw and len(words(desc)) <= 8:
            issues.append(_issue(
                "D004", f'Description "{desc}" adds nothing beyond the name `{label}`.',
                "Say what the tool returns and how it differs from similar tools.", label))
        # D005 is checked in lint_server: it only matters when a similar tool exists.

    # Input schema
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        issues.append(_issue(
            "S001", "inputSchema is missing or its type is not `object`.",
            'Provide a JSON Schema with `"type": "object"`, even if it has no properties.', label))
    else:
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for r in required:
            if r not in props:
                issues.append(_issue(
                    "S004", f"`required` lists `{r}`, which is not in `properties`.",
                    "Remove it from `required` or add the property.", label))
        if len(props) > MAX_PARAMS:
            issues.append(_issue(
                "S008", f"{len(props)} top-level parameters; models fill long forms less reliably.",
                "Split the tool, or group optional settings into one documented object.", label))
        too_deep: list[str] = []
        for path, prop, depth in walk_properties(schema):
            if depth > MAX_DEPTH:
                too_deep.append(path)
                continue
            if not _has_type(prop):
                issues.append(_issue(
                    "S002", f"Parameter `{path}` has no type.",
                    'Add a `type` (e.g. `"string"`), `enum` or `anyOf`.', label))
            if not (isinstance(prop.get("description"), str) and prop["description"].strip()):
                issues.append(_issue(
                    "S003", f"Parameter `{path}` has no description"
                    + (" (a `title` is not shown to most models)." if "title" in prop else "."),
                    "Describe the expected value and format, e.g. "
                    "`Annotated[str, Field(description=...)]` in Python.", label))
            ts = _types(prop)
            if "object" in ts and "properties" not in prop and prop.get("additionalProperties") is not False \
                    and "patternProperties" not in prop:
                issues.append(_issue(
                    "S005", f"Parameter `{path}` is a free-form object.",
                    "Declare its `properties`, or document the expected keys in its description.",
                    label))
            leaf = path.rsplit(".", 1)[-1].replace("[]", "").lower()
            if ts == {"string"} and leaf in ENUM_HINT_NAMES and "enum" not in prop:
                issues.append(_issue(
                    "S007", f"Parameter `{path}` probably accepts a fixed set of values.",
                    "List the allowed values with `enum` so the model cannot invent one.", label))
        if too_deep:
            issues.append(_issue(
                "S006", f"Parameters nested deeper than {MAX_DEPTH} levels: {', '.join(too_deep[:3])}"
                + (" ..." if len(too_deep) > 3 else "") + ".",
                "Flatten the structure; deep nesting is a common source of malformed calls.", label))

    # Annotations
    ann = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
    if "readOnlyHint" not in ann and "destructiveHint" not in ann:
        issues.append(_issue(
            "A001", "No `readOnlyHint` or `destructiveHint`, so clients cannot tell if it is safe.",
            "Set `readOnlyHint: true` for read-only tools, or `destructiveHint` for ones that "
            "modify or delete data.", label))
    elif ann.get("readOnlyHint") is True and ann.get("destructiveHint") is True:
        issues.append(_issue(
            "A002", "Marked both read-only and destructive.",
            "A read-only tool cannot be destructive; fix whichever hint is wrong.", label))
    return issues


def lint_server(
    tools: list[dict[str, Any]], token_counts: dict[int, int]
) -> tuple[list[Issue], dict[str, list[Issue]]]:
    """Return (server-level issues, tool-level issues found by comparing tools)."""
    issues: list[Issue] = []
    per_tool: dict[str, list[Issue]] = {}
    if not tools:
        return [_issue("X004", "The server lists no tools.",
                       "Check the server started correctly and registers its tools.", None)], per_tool

    names = [t.get("name") for t in tools if isinstance(t.get("name"), str) and t.get("name")]
    seen: set[str] = set()
    for n in names:
        if n in seen:
            issues.append(_issue("N002", f"Two or more tools are named `{n}`.",
                                 "Tool names must be unique within a server.", None))
        seen.add(n)

    styles = {name_style(n) for n in names if len(name_words(n)) > 1}
    if len(styles) > 1:
        issues.append(_issue(
            "N004", f"Tool names mix styles: {', '.join(sorted(styles))}.",
            "Pick one style (snake_case is most common) and use it for every tool.", None))

    if len(tools) > MAX_TOOLS:
        issues.append(_issue(
            "X003", f"{len(tools)} tools; tool-selection accuracy drops as the list grows.",
            "Split into focused servers, or merge near-duplicate tools.", None))

    total = sum(token_counts.values())
    if total > HEAVY_SERVER_TOKENS:
        issues.append(_issue(
            "X002", f"Tool definitions cost about {total:,} tokens on every turn.",
            "Trim long descriptions, remove unused tools, or split the server.", None))

    # Overlap: compare name + description vocabulary between every pair of tools.
    bags = []
    for t in tools[:300]:
        text = f"{' '.join(name_words(str(t.get('name', ''))))} {t.get('description') or ''}"
        bags.append((str(t.get("name", "?")), content_words(text), t.get("description") or ""))
    neighbour: dict[str, tuple[str, float]] = {}  # tool -> its most similar sibling
    for i in range(len(bags)):
        for j in range(i + 1, len(bags)):
            (na, a, _), (nb, b, _) = bags[i], bags[j]
            if len(a) < 3 or len(b) < 3:
                continue
            sim = len(a & b) / len(a | b)
            for x, y in ((na, nb), (nb, na)):
                if sim > neighbour.get(x, ("", 0.0))[1]:
                    neighbour[x] = (y, sim)
            if sim >= OVERLAP_THRESHOLD:
                issues.append(_issue(
                    "X001", f"`{na}` and `{nb}` are described almost the same way "
                    f"({sim:.0%} word overlap); a model may pick the wrong one.",
                    "Say in each description when to use it instead of the other, or merge them.",
                    None))

    # D005: "when to use" guidance matters when a similar tool exists to be confused with.
    for name, _, desc in bags:
        other, sim = neighbour.get(name, ("", 0.0))
        if sim >= SIMILAR_THRESHOLD and isinstance(desc, str) and len(desc.strip()) >= MIN_DESC_CHARS \
                and not (set(words(desc)) & USAGE_CUES):
            per_tool.setdefault(name, []).append(_issue(
                "D005", f"Similar to `{other}`, but the description doesn't say when to use this one.",
                f'Add a "Use this when ... (not `{other}`)" sentence.', name))
    return issues, per_tool


def heavy_tool_issue(name: str | None, tokens: int) -> Issue | None:
    if tokens > HEAVY_TOOL_TOKENS:
        return _issue("T001", f"This tool's definition is about {tokens:,} tokens.",
                      "Shorten the description and parameter docs; keep only what guides the model.",
                      name)
    return None
