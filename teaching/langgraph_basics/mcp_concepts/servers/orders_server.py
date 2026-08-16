"""A third MCP server, tools only, in a domain deliberately distinct from
calculator_server.py and knowledge_ops_server.py -- order lookups and
shipping, not math or service ops. Used together with the other two in
notebook 03 to demonstrate multi-server tool routing.

`check_status` on this server (and the identically-named `check_status` on
knowledge_ops_server.py) is a deliberately ambiguous pair, used only in
notebook 03 to show a real tool-selection mistake before fixing it with
clearer names -- `lookup_order_status` is the well-named equivalent an agent
should actually be given in a properly-scoped setup.

Run standalone (stdio transport, the default): `python orders_server.py`.
"""
from fastmcp import FastMCP

mcp = FastMCP("Orders")

_ORDERS = {
    "ORD-1001": {"status": "shipped", "eta_days": 2, "carrier": "FastShip"},
    "ORD-1002": {"status": "processing", "eta_days": None, "carrier": None},
    "ORD-1042": {"status": "delayed", "eta_days": 5, "carrier": "FastShip"},
}


@mcp.tool
def lookup_order_status(order_id: str) -> dict:
    """Look up the current status of a customer order by order ID (e.g. 'ORD-1001')."""
    if order_id not in _ORDERS:
        raise ValueError(f"Unknown order_id '{order_id}'. Known orders: {sorted(_ORDERS)}")
    return _ORDERS[order_id]


@mcp.tool
def get_shipping_estimate(order_id: str) -> dict:
    """Get the shipping ETA and carrier for a customer order by order ID."""
    if order_id not in _ORDERS:
        raise ValueError(f"Unknown order_id '{order_id}'. Known orders: {sorted(_ORDERS)}")
    record = _ORDERS[order_id]
    return {"eta_days": record["eta_days"], "carrier": record["carrier"]}


@mcp.tool
def check_status(id: str) -> str:
    """Check status by id. (Deliberately vague -- see module docstring; used only
    in notebook 03's tool-naming-collision demo, not in notebooks 01/02.)"""
    if id not in _ORDERS:
        raise ValueError(f"Unknown order_id '{id}'. Known orders: {sorted(_ORDERS)}")
    return _ORDERS[id]["status"]


if __name__ == "__main__":
    mcp.run()
