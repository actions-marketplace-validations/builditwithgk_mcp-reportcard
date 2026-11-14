from mcp_doctor import analyze, load_tools
from mcp_doctor.loader import LoadError
from mcp_doctor.rules import lint_server, lint_tool, name_style

import pytest


def good_tool(**overrides):
    tool = {
        "name": "get_order",
        "description": "Return the status and total of one order. Use this when you have the exact ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order ID, digits only."}},
            "required": ["order_id"],
        },
        "annotations": {"readOnlyHint": True},
    }
    tool.update(overrides)
    return tool


def rules_of(issues):
    return sorted(i.rule for i in issues)


def test_clean_tool_has_no_issues():
    assert lint_tool(good_tool()) == []


@pytest.mark.parametrize("tool, rule", [
    (good_tool(name=""), "N001"),
    (good_tool(name="get order!"), "N003"),
    (good_tool(name="x" * 70), "N005"),
    (good_tool(description=""), "D001"),
    (good_tool(description="Gets it."), "D002"),
    (good_tool(description="x" * 1100 + " use"), "D003"),
    (good_tool(description="Get order"), "D004"),
    (good_tool(inputSchema={"type": "string"}), "S001"),
    (good_tool(inputSchema={"type": "object", "properties": {"a": {"description": "x"}}}), "S002"),
    (good_tool(inputSchema={"type": "object", "properties": {"a": {"type": "string", "title": "A"}}}), "S003"),
    (good_tool(inputSchema={"type": "object", "properties": {}, "required": ["ghost"]}), "S004"),
    (good_tool(inputSchema={"type": "object", "properties": {"cfg": {"type": "object", "description": "x"}}}), "S005"),
    (good_tool(inputSchema={"type": "object", "properties": {"mode": {"type": "string", "description": "x"}}}), "S007"),
    (good_tool(inputSchema={"type": "object", "properties": {
        f"p{i}": {"type": "string", "description": "x"} for i in range(11)}}), "S008"),
    (good_tool(annotations={}), "A001"),
    (good_tool(annotations={"readOnlyHint": True, "destructiveHint": True}), "A002"),
])
def test_each_rule_fires(tool, rule):
    assert rule in rules_of(lint_tool(tool))


def test_deep_nesting_flagged():
    leaf = {"type": "string", "description": "x"}
    schema = {"type": "object", "properties": {"a": {"type": "object", "description": "x", "properties": {
        "b": {"type": "object", "description": "x", "properties": {
            "c": {"type": "object", "description": "x", "properties": {"d": leaf}}}}}}}}
    assert "S006" in rules_of(lint_tool(good_tool(inputSchema=schema)))


def test_server_rules():
    a = good_tool(name="find_items", description="Search the store catalogue items by keyword and return matches.")
    b = good_tool(name="search_items", description="Search store catalogue items by keyword and return matching items.")
    c = good_tool(name="getCustomer")
    issues, _ = lint_server([a, b, c, dict(a)], {0: 10, 1: 10, 2: 10, 3: 10})
    assert {"N002", "N004", "X001"} <= set(rules_of(issues))
    assert rules_of(lint_server([], {})[0]) == ["X004"]
    assert "X002" in rules_of(lint_server([good_tool()], {0: 20_000})[0])
    many = [good_tool(name=f"tool_{i}", description=f"Unique purpose number {i} {'z' * i}") for i in range(41)]
    assert "X003" in rules_of(lint_server(many, {})[0])


def test_usage_guidance_only_when_a_similar_tool_exists():
    lone = good_tool(name="get_weather", description="Returns the current weather forecast for a city.")
    _, per_tool = lint_server([lone], {})
    assert per_tool == {}  # nothing to confuse it with, so no D005

    a = good_tool(name="search_orders", description="Search customer orders by keyword and return order IDs.")
    b = good_tool(name="search_invoices", description="Search customer invoices by keyword and return invoice IDs.")
    _, per_tool = lint_server([a, b], {})
    assert [i.rule for i in per_tool["search_orders"]] == ["D005"]

    guided = dict(b, description=b["description"] + " Use this when the user asks about billing.")
    _, per_tool = lint_server([a, guided], {})
    assert "search_invoices" not in per_tool


def test_name_style():
    assert name_style("get_order") == "snake_case"
    assert name_style("getOrder") == "camelCase"
    assert name_style("get-order") == "kebab-case"


def test_loader_shapes():
    tool = good_tool()
    assert load_tools([tool]) == [tool]
    assert load_tools({"tools": [tool]}) == [tool]
    assert load_tools({"jsonrpc": "2.0", "id": 1, "result": {"tools": [tool]}}) == [tool]
    with pytest.raises(LoadError):
        load_tools({"nope": 1})
    with pytest.raises(LoadError):
        load_tools([1, 2])


def test_scoring_and_grades():
    perfect = analyze([good_tool()], server="x")
    assert (perfect.score, perfect.grade) == (100, "A")
    broken = analyze([{"name": "x"}], server="x")
    assert broken.score < 60 and broken.grade == "F"
    assert analyze([], server="x").score == 0


def test_report_serialises():
    from mcp_doctor.report import to_json, to_markdown

    r = analyze([good_tool(), good_tool(name="b", description="")], server="demo")
    assert '"grade"' in to_json(r)
    md = to_markdown(r)
    assert "MCP Doctor report" in md and "D001" in md
