"""Run every check over a tool list and turn the results into a scored report."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from mcp_doctor import rules, tokens
from mcp_doctor.models import FuzzOutcome, Issue, Report, Severity, ToolResult

TOOL_PENALTY = {Severity.ERROR: 25, Severity.WARNING: 10, Severity.INFO: 3}
SERVER_PENALTY = {Severity.ERROR: 10, Severity.WARNING: 5, Severity.INFO: 1}
SERVER_PENALTY_CAP = 40


def grade(score: int) -> str:
    for cutoff, g in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= cutoff:
            return g
    return "F"


def fuzz_issues(outcomes: list[FuzzOutcome]) -> dict[str, list[Issue]]:
    """Collapse fuzz outcomes into at most one issue per tool per failure kind."""
    by_tool: dict[str, dict[str, list[FuzzOutcome]]] = defaultdict(lambda: defaultdict(list))
    for o in outcomes:
        by_tool[o.case.tool][o.status].append(o)

    out: dict[str, list[Issue]] = defaultdict(list)
    for tool, kinds in by_tool.items():
        if kinds.get("accepted"):
            cases = ", ".join(o.case.label for o in kinds["accepted"][:3])
            out[tool].append(Issue(
                "F001", Severity.WARNING,
                f"Accepted input that breaks its own schema without returning an error ({cases}).",
                "Validate arguments against the schema and return `isError: true` with a clear "
                "message the model can act on.", tool))
        if kinds.get("leaked"):
            out[tool].append(Issue(
                "F002", Severity.ERROR,
                f"Error output exposes internals: {kinds['leaked'][0].detail}",
                "Log stack traces server-side; return a short, safe message to the client.", tool))
        bad = kinds.get("crashed", []) + kinds.get("timeout", [])
        if bad:
            first = bad[0]
            out[tool].append(Issue(
                "F003", Severity.ERROR,
                f"{first.status.capitalize()} on `{first.case.label}`: {first.detail}",
                "Catch exceptions inside the tool and return `isError: true`; add timeouts to "
                "slow calls.", tool))
    return out


def analyze(
    tools: list[dict[str, Any]],
    server: str = "server",
    fuzz_outcomes: list[FuzzOutcome] | None = None,
    fuzz_skipped: list[str] | None = None,
) -> Report:
    fuzz_outcomes = fuzz_outcomes or []
    from_fuzz = fuzz_issues(fuzz_outcomes)

    token_counts = {idx: tokens.count_tool_tokens(tool) for idx, tool in enumerate(tools)}
    server_issues, cross_tool = rules.lint_server(tools, token_counts)

    results: list[ToolResult] = []
    for idx, tool in enumerate(tools):
        name = tool.get("name") if isinstance(tool.get("name"), str) and tool.get("name") else None
        n_tokens = token_counts[idx]
        issues = rules.lint_tool(tool)
        heavy = rules.heavy_tool_issue(name, n_tokens)
        if heavy:
            issues.append(heavy)
        if name:
            issues.extend(cross_tool.get(name, []))
            issues.extend(from_fuzz.get(name, []))
        penalty = sum(TOOL_PENALTY[i.severity] for i in issues)
        results.append(ToolResult(
            name=name or f"<unnamed #{idx + 1}>",
            score=max(0, 100 - penalty),
            tokens=n_tokens,
            issues=issues,
        ))

    if results:
        base = sum(r.score for r in results) / len(results)
        penalty = min(SERVER_PENALTY_CAP, sum(SERVER_PENALTY[i.severity] for i in server_issues))
        score = max(0, round(base - penalty))
    else:
        score = 0

    return Report(
        server=server,
        score=score,
        grade=grade(score),
        tools=results,
        server_issues=server_issues,
        total_tokens=sum(token_counts.values()),
        token_method=tokens.method(),
        fuzz_outcomes=fuzz_outcomes,
        fuzz_skipped=fuzz_skipped or [],
    )
