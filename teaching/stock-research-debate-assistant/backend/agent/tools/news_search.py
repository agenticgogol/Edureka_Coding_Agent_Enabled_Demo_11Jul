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
import json
import os
import re
import threading
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config import config


class NewsSearchError(RuntimeError):
    """Raised when the tavily-mcp call fails or the key is missing."""


# In-process short-TTL cache keyed by (ticker, query): a fresh
# tavily-mcp subprocess is expensive to spawn (npx cold start + a real
# web search call), and the same ticker/query is commonly re-looked-up
# within one session (e.g. a follow_up re-derives the same news query, or
# two turns in a row both need AAPL news). This does not replace the
# fetched_data-freshness check in graph.py (that governs whether the
# fetch node runs at all) — this cache covers repeated calls that reach
# this module directly with the same key even across different fetch
# nodes/tickers-in-a-comparison.
_CACHE_TTL_SECONDS = 8 * 60
_cache_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, dict]] = {}

# graph.py fans `fetch_news` out per-ticker via parallel LangGraph `Send`s (a
# multi-ticker comparison dispatches several at once). Each call does
# asyncio.run(...) to spawn the tavily-mcp subprocess via anyio — spawning a
# subprocess concurrently from more than one freshly-created event loop hits
# anyio's "Racing with another loop to spawn a process" error. Serialize the
# spawn itself (not the whole cached lookup) so concurrent tickers queue
# instead of racing; each still gets its own real, uncached result.
_spawn_lock = threading.Lock()


def _cache_get(key: tuple[str, str]) -> dict | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        cached_at, value = entry
        if (time.time() - cached_at) >= _CACHE_TTL_SECONDS:
            del _cache[key]
            return None
        return value


def _cache_set(key: tuple[str, str], value: dict) -> None:
    with _cache_lock:
        _cache[key] = (time.time(), value)


def _server_params() -> StdioServerParameters:
    config.require_tavily_key()
    env = dict(os.environ)
    env["TAVILY_API_KEY"] = config.tavily_api_key
    return StdioServerParameters(command="npx", args=["-y", "tavily-mcp"], env=env)


_URL_RE = re.compile(r"https?://[^\s\)\]\"']+")


def _parse_sources(content_items, text_parts: list[str]) -> list[dict]:
    """Extract structured {title, url} source pairs from a tavily-mcp
    result. Tries, in order: a JSON-typed content block with a `results`
    list (title/url pairs), a JSON object embedded in a text block (tavily
    commonly returns its results as a JSON string inside a text part), and
    finally a regex URL fallback (title unknown) so sources are never
    silently discarded even if the shape drifts.
    """
    for item in content_items:
        data = getattr(item, "data", None)
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return [
                {"title": r.get("title"), "url": r.get("url")}
                for r in data["results"]
                if isinstance(r, dict) and r.get("url")
            ]

    for text in text_parts:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        results = parsed.get("results") if isinstance(parsed, dict) else None
        if isinstance(results, list):
            sources = [
                {"title": r.get("title"), "url": r.get("url")}
                for r in results
                if isinstance(r, dict) and r.get("url")
            ]
            if sources:
                return sources

    urls = []
    seen = set()
    for text in text_parts:
        for url in _URL_RE.findall(text):
            url = url.rstrip(".,;")
            if url not in seen:
                seen.add(url)
                urls.append({"title": None, "url": url})
    return urls


async def _search_async(query: str, max_results: int) -> tuple[str, list[dict]]:
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
            sources = _parse_sources(result.content, text_parts)
            return "\n".join(text_parts), sources


def fetch_news(ticker: str, query_hint: str | None = None, max_results: int = 5) -> dict:
    """Runs one tavily-mcp search for recent news relevant to `ticker`.

    `query_hint` lets the orchestrator pass a more specific query (e.g.
    "AAPL earnings guidance") instead of a generic ticker name search.
    """
    query = query_hint or f"{ticker} stock recent news"
    cache_key = (ticker.strip().upper(), query)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        with _spawn_lock:
            raw_text, sources = asyncio.run(_search_async(query, max_results))
    except NewsSearchError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise NewsSearchError(
            f"tavily-mcp call failed for '{ticker}': {exc!r}"
        ) from exc
    result = {"ticker": ticker, "query": query, "raw_results": raw_text, "sources": sources}
    _cache_set(cache_key, result)
    return result
