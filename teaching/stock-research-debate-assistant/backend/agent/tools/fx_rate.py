"""Real MCP client for FX conversion, via the Frankfurter Forex MCP server
(anirbanbasu/frankfurtermcp on PyPI, wraps the free ECB-backed Frankfurter
API — no API key required).

Verified live against the project's GitHub README on 2026-08-29:
  - install: `pip install frankfurtermcp`
  - stdio launch: `python -m frankfurtermcp.server` (stdio is the module's
    default transport; `MCP_SERVER_TRANSPORT=stdio` is set explicitly here
    anyway, for a reproducible subprocess rather than relying on the
    library's default)
  - no API key required
  - relevant exposed tool used here: `convert_currency_latest`
    (other tools available: get_supported_currencies,
    get_latest_exchange_rates, get_historical_exchange_rates,
    convert_currency_specific_date, greet)

NOTE: the exact JSON argument names for `convert_currency_latest` were not
directly enumerated in the fetched README (it documented the tool list and
transport, not the per-tool JSON schema). This module calls it with the
conventional `{"amount": ..., "from_currency": ..., "to_currency": ...}`
shape; the flag if this is a real risk is called out in the parent report.
"""
from __future__ import annotations

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class FxRateError(RuntimeError):
    """Raised when the Frankfurter MCP call fails."""


def _server_params() -> StdioServerParameters:
    env = dict(os.environ)
    env["MCP_SERVER_TRANSPORT"] = "stdio"
    return StdioServerParameters(command="python", args=["-m", "frankfurtermcp.server"], env=env)


async def _convert_async(amount: float, from_currency: str, to_currency: str) -> str:
    params = _server_params()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "convert_currency_latest",
                arguments={
                    "amount": amount,
                    "from_currency": from_currency.upper(),
                    "to_currency": to_currency.upper(),
                },
            )
            if getattr(result, "isError", False):
                raise FxRateError(
                    f"Frankfurter MCP returned an error converting {from_currency}->{to_currency}: {result.content}"
                )
            text_parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
            if not text_parts:
                raise FxRateError(f"Frankfurter MCP returned no text content for {from_currency}->{to_currency}.")
            return "\n".join(text_parts)


def fetch_fx_rate(from_currency: str, to_currency: str, amount: float = 1.0) -> dict:
    """Fetches a live mid-market conversion between two currencies.

    Used only when a comparison spans currencies (e.g. USD vs INR
    tickers) — the orchestrator decides whether this tool is needed.
    """
    if from_currency.upper() == to_currency.upper():
        return {"from_currency": from_currency.upper(), "to_currency": to_currency.upper(), "rate": 1.0, "amount": amount, "converted": amount}
    try:
        raw_text = asyncio.run(_convert_async(amount, from_currency, to_currency))
    except FxRateError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FxRateError(f"Frankfurter MCP call failed for {from_currency}->{to_currency}: {exc}") from exc
    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "amount": amount,
        "raw_result": raw_text,
    }
