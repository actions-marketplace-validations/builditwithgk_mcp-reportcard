"""A deliberately sloppy MCP server for demos and tests. Every tool has a common mistake.

Run:  mcp-doctor check "python examples/bad_server.py" --fuzz
"""

import traceback

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

server = MCPServer("acme-orders (bad example)")

ORDERS = {"1001": {"status": "shipped", "total": 49.0}, "1002": {"status": "pending", "total": 12.5}}


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def search(query: str, mode: str = "fuzzy") -> list[str]:
    """Search."""  # too short, `mode` should be an enum, no parameter descriptions
    return [oid for oid in ORDERS if query in oid]


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def find_items(keyword: str) -> list[str]:
    """Search the store catalogue items by keyword and return the matching items."""
    return []


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def search_items(keyword: str) -> list[str]:
    """Search store catalogue items by keyword and return matching catalogue items."""
    return []  # near-duplicate of find_items: the model can't tell which to use


@server.tool()
def getCustomer(id: str) -> dict:  # noqa: N802  camelCase mixed with snake_case, no annotations
    """Get customer"""
    return {"id": id}


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def lookup_invoice(invoice_id: str) -> dict:
    """Look up an invoice by its numeric ID and return the amount due."""
    try:
        n = int(invoice_id)
        return {"invoice": n, "due": 0}
    except Exception:
        raise ToolError(traceback.format_exc())  # leaks a stack trace and file paths


@server.tool()
def delete_order(order_id: str) -> str:
    """Deletes an order permanently."""  # destructive, but not annotated as such
    ORDERS.pop(order_id, None)
    return "deleted"


@server.tool()
def update_settings(settings: dict) -> str:
    """Update account settings."""  # free-form object: the model must guess the keys
    return "ok"


if __name__ == "__main__":
    server.run()
