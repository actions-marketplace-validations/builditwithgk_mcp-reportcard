import sys
from pathlib import Path

import anyio
import pytest

from mcp_reportcard.analyze import analyze
from mcp_reportcard.connect import fetch_tools
from mcp_reportcard.fuzz import classify, find_leak, is_safe_to_fuzz, make_cases, run_fuzz, sample_value
from mcp_reportcard.models import FuzzCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
import bad_server  # noqa: E402
import good_server  # noqa: E402


def test_leak_detection():
    assert find_leak('Traceback (most recent call last):\n  File "x.py", line 3, in run')
    assert find_leak("TypeError: bad\n    at handler (/home/app/index.js:10:5)")
    assert find_leak("Error: x\n    at C:\\srv\\app\\dist\\index.js:4:11")
    assert find_leak("NullPointerException\n\tat com.acme.Svc.run(Svc.java:42)")
    assert find_leak("Order 1001 not found") is None
    assert find_leak("see https://errors.pydantic.dev/2.1/v/missing") is None


def test_helpful_paths_are_not_leaks():
    # Real messages from the official filesystem and git servers: paths, but no stack trace.
    assert find_leak(r"ENOENT: no such file or directory, lstat 'C:\work\sandbox\notes.txt'") is None
    assert find_leak("Repository path 'x' is outside the allowed repository '/home/me/repo'") is None


def test_classify():
    bad = FuzzCase("t", "wrong type", {}, True)
    edge = FuzzCase("t", "long string", {}, False)
    assert classify(bad, is_error=True, text="invalid").status == "rejected"
    assert classify(bad, is_error=False, text="ok").status == "accepted"
    assert classify(edge, is_error=False, text="ok").status == "ok"
    assert classify(edge, is_error=True, text='File "a.py", line 1, in main').status == "leaked"


def test_safety_gate():
    assert is_safe_to_fuzz({"annotations": {"readOnlyHint": True}})
    assert not is_safe_to_fuzz({"annotations": {"readOnlyHint": True, "destructiveHint": True}})
    assert not is_safe_to_fuzz({})


def test_case_generation():
    tool = {"name": "t", "inputSchema": {"type": "object", "required": ["n"], "properties": {
        "n": {"type": "integer"}, "mode": {"type": "string", "enum": ["a", "b"]}, "q": {"type": "string"}}}}
    labels = [c.label for c in make_cases(tool)]
    assert "missing required arguments" in labels
    assert "wrong type for `n`" in labels
    assert "value outside enum for `mode`" in labels
    assert "10k-char string for `q`" in labels
    assert sample_value({"type": "integer", "minimum": 5}) == 5


def _check(server):
    async def go():
        name, tools = await fetch_tools(server)
        outcomes, skipped = await run_fuzz(server, tools)
        return analyze(tools, server=name, fuzz_outcomes=outcomes, fuzz_skipped=skipped)
    return anyio.run(go)


def test_bad_server_end_to_end():
    report = _check(bad_server.server)
    rules = {i.rule for i in report.all_issues}
    assert {"F002", "X001", "N004", "A001", "S003", "S005"} <= rules
    assert set(report.fuzz_skipped) == {"getCustomer", "delete_order", "update_settings"}
    assert report.grade in {"D", "F"}


def test_good_server_end_to_end():
    report = _check(good_server.server)
    assert report.grade == "A", [i.to_dict() for i in report.all_issues]
    assert report.fuzz_skipped == ["cancel_order"]
    assert report.fuzz_outcomes and all(o.status in {"ok", "rejected"} for o in report.fuzz_outcomes)


@pytest.mark.parametrize("example", ["good_server.py"])
def test_stdio_connection(example):
    """Launch an example as a real subprocess over stdio, the way users run the CLI."""
    script = Path(__file__).resolve().parents[1] / "examples" / example
    name, tools = anyio.run(fetch_tools, f'"{sys.executable}" "{script}"')
    assert "good example" in name and len(tools) == 3
