"""An MCP server exposing all three MCP primitives -- tools, resources, and
prompts -- backed by small synthetic ops data (no real infrastructure, no
paid APIs). Services mirror multi_agent_architectures' incident-investigation
theme (checkout/payments/search/inventory/auth) for continuity across this
course.

Run standalone (stdio transport, the default): `python knowledge_ops_server.py`.
Notebook 01 also shows launching this same server with `transport="http"` for
the transport-comparison discussion.
"""
from fastmcp import FastMCP

mcp = FastMCP("KnowledgeOps")

_SERVICES = {"checkout", "payments", "search", "inventory", "auth"}

_RUNBOOKS = {
    "checkout": (
        "# Checkout Service Runbook\n"
        "1. Check payment-gateway timeout metrics first -- checkout errors are\n"
        "   most often caused by upstream payment latency, not checkout itself.\n"
        "2. Check for a recent deploy in the last 60 minutes.\n"
        "3. If cart-lock conflicts appear in logs, restart the cart-lock service."
    ),
    "payments": (
        "# Payments Service Runbook\n"
        "1. Check card-issuer timeout rate -- a spike usually means an upstream\n"
        "   acquirer bank issue, not a bug in our code.\n"
        "2. Check acquirer-bank status pages before escalating internally."
    ),
    "search": (
        "# Search Service Runbook\n"
        "1. Check p99 query latency against the 400ms baseline.\n"
        "2. Check for a recent index-shard rebalance or deploy.\n"
        "3. Latency-only (no errors) usually means a shard rebalance in progress."
    ),
    "inventory": (
        "# Inventory Service Runbook\n"
        "1. Check the stock-sync job's last successful run timestamp.\n"
        "2. Discrepancies usually clear within one sync cycle (15 min)."
    ),
    "auth": (
        "# Auth Service Runbook\n"
        "1. Check SSO token validation error rate.\n"
        "2. Check MFA provider status -- a third-party MFA outage is the most\n"
        "   common cause of a login spike."
    ),
}

_ONCALL_CONTACTS = {
    "checkout": "Priya K. (#checkout-oncall, priya.k@example.com)",
    "payments": "Sam T. (#payments-oncall, sam.t@example.com)",
    "search": "Jordan L. (#search-oncall, jordan.l@example.com)",
    "inventory": "Ravi N. (#inventory-oncall, ravi.n@example.com)",
    "auth": "Dana W. (#auth-oncall, dana.w@example.com)",
}

_STATUS = {
    "checkout": {"status": "degraded", "error_rate_pct": 18.4, "last_deploy_minutes_ago": 40},
    "payments": {"status": "degraded", "error_rate_pct": 22.1, "last_deploy_minutes_ago": None},
    "search": {"status": "degraded", "error_rate_pct": 0.3, "last_deploy_minutes_ago": 25},
    "inventory": {"status": "healthy", "error_rate_pct": 0.4, "last_deploy_minutes_ago": None},
    "auth": {"status": "degraded", "error_rate_pct": 9.7, "last_deploy_minutes_ago": 120},
}


# ---------------------------------------------------------------------------
# Tools -- actions the agent invokes to DO something (fetch live-ish data).
# ---------------------------------------------------------------------------

@mcp.tool
def search_runbooks(query: str) -> list[str]:
    """Search runbook titles for services matching a keyword (e.g. 'payment', 'login')."""
    query_lower = query.lower()
    return [s for s in _SERVICES if query_lower in s or s in query_lower]


@mcp.tool
def get_service_status(service: str) -> dict:
    """Get the current status, error rate, and last deploy time for a service."""
    if service not in _STATUS:
        raise ValueError(f"Unknown service '{service}'. Known services: {sorted(_SERVICES)}")
    return _STATUS[service]


@mcp.tool
def check_status(id: str) -> str:
    """Check status by id. (Deliberately vague -- see orders_server.py's module
    docstring; used only in notebook 03's tool-naming-collision demo, not in
    notebooks 01/02.)"""
    if id not in _STATUS:
        raise ValueError(f"Unknown service '{id}'. Known services: {sorted(_SERVICES)}")
    return _STATUS[id]["status"]


# ---------------------------------------------------------------------------
# Resources -- addressable, mostly-static data the client can read directly,
# without going through an LLM tool-call decision. Static URI vs. a dynamic
# template URI (`{service}` is filled in per request).
# ---------------------------------------------------------------------------

@mcp.resource("resource://team/oncall-contacts")
def oncall_contacts() -> dict:
    """The full on-call contact list, one entry per service."""
    return _ONCALL_CONTACTS


@mcp.resource("runbook://{service}/latest")
def runbook_for_service(service: str) -> str:
    """The latest runbook document for one specific service."""
    if service not in _RUNBOOKS:
        raise ValueError(f"No runbook for '{service}'. Known services: {sorted(_SERVICES)}")
    return _RUNBOOKS[service]


# ---------------------------------------------------------------------------
# Prompts -- reusable, parameterized message templates the *user* (or a
# client UI) selects, distinct from tools (which the *model* decides to call).
# ---------------------------------------------------------------------------

@mcp.prompt
def incident_summary_prompt(service: str, symptom: str) -> str:
    """Generates a ready-to-send prompt asking for an incident summary for one service."""
    return (
        f"Write a concise incident summary for the '{service}' service. "
        f"Reported symptom: '{symptom}'. Include: likely root cause, "
        f"recommended next diagnostic step, and who to page."
    )


if __name__ == "__main__":
    import sys

    # `python knowledge_ops_server.py` -> stdio (default, used in notebooks 01/02/03).
    # `python knowledge_ops_server.py --http [port]` -> Streamable HTTP, used in
    # notebook 01's transport-comparison section to show the same server, same
    # tools/resources/prompts, reachable a second way.
    if "--http" in sys.argv:
        idx = sys.argv.index("--http")
        port = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 8931
        mcp.run(transport="http", port=port)
    else:
        mcp.run()
