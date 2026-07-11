"""Minimal REAL MCP server — a genuine separate process over stdio
transport, not an in-process function call.

Verify against current `mcp` package docs (research-first) — server
construction API has evolved. Install: pip install mcp.
Run standalone: python mcp_server.py
"""
from __future__ import annotations

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("demo-mcp-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="lookup_order_status",
            description="Look up the status of an order by ID",
            inputSchema={
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "lookup_order_status":
        order_id = arguments["order_id"]
        # Replace with a real lookup (e.g. a DB query) for the actual project.
        return [TextContent(type="text", text=f"Order {order_id}: shipped")]
    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
