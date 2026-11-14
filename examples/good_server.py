"""The same order service as bad_server.py, written so mcp-reportcard gives it an A.

Run:  mcp-reportcard check "python examples/good_server.py" --fuzz
"""

from typing import Annotated, Literal

from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

server = MCPServer("acme-orders (good example)")

ORDERS = {"1001": {"status": "shipped", "total": 49.0}, "1002": {"status": "pending", "total": 12.5}}

OrderId = Annotated[str, Field(description="Order ID, digits only, e.g. '1001'.", pattern=r"^\d+$")]


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def search_orders(
    query: Annotated[str, Field(description="Text to match against order IDs.", max_length=100)],
    status: Annotated[
        Literal["any", "pending", "shipped"], Field(description="Only return orders in this status.")
    ] = "any",
) -> list[str]:
    """Find orders whose ID contains the query text and return their IDs.
    Use this when the user does not know the exact order ID; use get_order when they do."""
    return [oid for oid, o in ORDERS.items() if query in oid and status in ("any", o["status"])]


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def get_order(order_id: OrderId) -> dict:
    """Return the status and total of one order. Use this when you already have the exact order ID."""
    order = ORDERS.get(order_id)
    if order is None:
        raise ToolError(f"No order with ID {order_id}. Use search_orders to find the right ID.")
    return {"order_id": order_id, **order}


@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True))
def cancel_order(
    order_id: OrderId,
    reason: Annotated[str, Field(description="Short reason shown to the customer.", max_length=200)],
) -> str:
    """Cancel a pending order. Only use this after the user has explicitly confirmed the
    cancellation; shipped orders cannot be cancelled."""
    order = ORDERS.get(order_id)
    if order is None or order["status"] != "pending":
        raise ToolError("Only existing pending orders can be cancelled.")
    order["status"] = "cancelled"
    return f"Order {order_id} cancelled."


if __name__ == "__main__":
    server.run()
