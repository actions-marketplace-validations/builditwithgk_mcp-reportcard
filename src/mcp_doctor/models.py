"""Data types shared by every part of MCP Doctor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Issue:
    rule: str
    severity: Severity
    message: str
    fix: str
    tool: str | None = None  # None means a server-level issue

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class ToolResult:
    name: str
    score: int
    tokens: int
    issues: list[Issue] = field(default_factory=list)


@dataclass
class FuzzCase:
    tool: str
    label: str
    arguments: dict[str, Any]
    expect_error: bool  # True when the input violates the schema


@dataclass
class FuzzOutcome:
    case: FuzzCase
    status: str  # rejected | accepted | leaked | crashed | timeout | ok
    detail: str = ""


@dataclass
class Report:
    server: str
    score: int
    grade: str
    tools: list[ToolResult]
    server_issues: list[Issue]
    total_tokens: int
    token_method: str
    fuzz_outcomes: list[FuzzOutcome] = field(default_factory=list)
    fuzz_skipped: list[str] = field(default_factory=list)

    @property
    def all_issues(self) -> list[Issue]:
        out = list(self.server_issues)
        for t in self.tools:
            out.extend(t.issues)
        return out

    def counts(self) -> dict[str, int]:
        c = {s.value: 0 for s in Severity}
        for i in self.all_issues:
            c[i.severity.value] += 1
        return c

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "score": self.score,
            "grade": self.grade,
            "counts": self.counts(),
            "total_tokens": self.total_tokens,
            "token_method": self.token_method,
            "server_issues": [i.to_dict() for i in self.server_issues],
            "tools": [
                {
                    "name": t.name,
                    "score": t.score,
                    "tokens": t.tokens,
                    "issues": [i.to_dict() for i in t.issues],
                }
                for t in self.tools
            ],
            "fuzz": {
                "outcomes": [
                    {
                        "tool": o.case.tool,
                        "case": o.case.label,
                        "arguments": o.case.arguments,
                        "status": o.status,
                        "detail": o.detail,
                    }
                    for o in self.fuzz_outcomes
                ],
                "skipped_tools": self.fuzz_skipped,
            },
        }
