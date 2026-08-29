"""Real MCP client for news search, via `tavily-mcp` (npm, stdio).

Verified live against Tavily's own MCP docs (docs.tavily.com/documentation/mcp)
and the `tavily-mcp` npm package page on 2026-08-29:
  - package: `tavily-mcp` (published by tavily-ai), local stdio variant
  - launch: `npx -y tavily-mcp` over stdio (no version pin — the docs'
    sample pins a version, e.g. `tavily-mcp@0.1.3`, but that pin drifts;
    unpinned `npx -y tavily-mcp` always resolves the current published
    version, which is the safer default for a teaching demo)
  - required env var: `TAVILY_API_KEY` (format `tvly-...`), passed to the
    subprocess environment
  - the server has exposed both `tavily-search` and `tavily_search` across
    published versions — this client discovers the installed spelling

The client discovers the installed search-tool name before calling it. This
handles the hyphenated and underscored names used by different releases
without fabricating a result or hiding a subprocess error.
"""
from __future__ import annotations

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config import config


class NewsSearchError(RuntimeError):
    """Raised when the tavily-mcp call fails or the key is missing."""


def _server_params() -> StdioServerParameters:
    config.require_tavily_key()
    env = dict(os.environ)
    env["TAVILY_API_KEY"] = config.tavily_api_key
    return StdioServerParameters(command="npx", args=["-y", "tavily-mcp"], env=env)


async def _search_async(query: str, max_results: int) -> str:
    params = _server_params()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            available = [tool.name for tool in tools.tools]
            tool_name = next(
                (name for name in ("tavily-search", "tavily_search") if name in available),
                None,
            )
            if tool_name is None:
                raise NewsSearchError(
                    "tavily-mcp started but exposed no supported search tool. "
                    f"Available tools: {available or '(none)'}"
                )
            result = await session.call_tool(
                tool_name, arguments={"query": query, "max_results": max_results}
            )
            if getattr(result, "isError", False):
                raise NewsSearchError(f"tavily-mcp returned an error for query '{query}': {result.content}")
            text_parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
            if not text_parts:
                raise NewsSearchError(f"tavily-mcp returned no text content for query '{query}'.")
            return "\n".join(text_parts)


def fetch_news(ticker: str, query_hint: str | None = None, max_results: int = 5) -> dict:
    """Runs one tavily-mcp search for recent news relevant to `ticker`.

    `query_hint` lets the orchestrator pass a more specific query (e.g.
    "AAPL earnings guidance") instead of a generic ticker name search.
    """
    query = query_hint or f"{ticker} stock recent news"
    try:
        raw_text = asyncio.run(_search_async(query, max_results))
    except NewsSearchError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise NewsSearchError(
            f"tavily-mcp call failed for '{ticker}': {exc!r}"
        ) from exc
    return {"ticker": ticker, "query": query, "raw_results": raw_text}
