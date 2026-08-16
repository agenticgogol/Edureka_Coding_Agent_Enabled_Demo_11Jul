"""A minimal MCP server demonstrating *sampling*: the server itself asks the
CLIENT's LLM to generate text via `ctx.sample()`, instead of holding its own
API key. Used only in notebook 05's advanced-concepts section.

Run standalone (stdio transport): `python sampling_demo_server.py`.
"""
from fastmcp import FastMCP, Context

mcp = FastMCP("SamplingDemo")


@mcp.tool
async def summarize_via_client_llm(text: str, ctx: Context) -> str:
    """Ask the CLIENT's own LLM (not this server) to summarize the given text
    in one sentence. Demonstrates MCP sampling -- the server has no API key
    of its own and never calls a model directly."""
    result = await ctx.sample(
        messages=f"Summarize this in exactly one sentence:\n\n{text}",
        max_tokens=100,
    )
    return result.text if hasattr(result, "text") else str(result)


if __name__ == "__main__":
    mcp.run()
