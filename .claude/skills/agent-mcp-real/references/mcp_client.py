"""Minimal REAL MCP client — spawns the server as a genuine separate
process over stdio, performs capability negotiation, and calls a tool.

Verify against current `mcp` package docs (research-first). Install:
pip install mcp. Run standalone: python mcp_client.py
(expects mcp_server.py in the same directory)
"""
from __future__ import annotations

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_lookup_order(order_id: str) -> str:
    server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    params = StdioServerParameters(command="python", args=[server_path])

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()  # capability negotiation happens here

            tools = await session.list_tools()
            assert any(t.name == "lookup_order_status" for t in tools.tools), (
                "server did not advertise expected tool — capability "
                "negotiation succeeded but tool list is wrong"
            )

            result = await session.call_tool(
                "lookup_order_status", arguments={"order_id": order_id}
            )
            return result.content[0].text


def run_agent(order_id: str) -> str:
    """Entrypoint the backend calls — wraps the async client in a sync call."""
    return asyncio.run(call_lookup_order(order_id))


if __name__ == "__main__":
    print("Client -> Server -> Client round trip:")
    print(run_agent("A-1001"))
