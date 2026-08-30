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

Argument names and response schema verified directly against the installed
`frankfurtermcp` package source (`frankfurtermcp/server.py` and
`frankfurtermcp/model.py`, package version 0.4.0.post1) rather than a live
call:
  - `convert_currency_latest(ctx, amount: PositiveFloat, from_currency:
    ISO4217, to_currency: ISO4217)` — confirms the `amount`/`from_currency`/
    `to_currency` argument names used below are correct.
  - The tool raises a `ValueError` server-side if `from_currency ==
    to_currency` (case-insensitive) — this module already short-circuits
    that case locally in `fetch_fx_rate` before calling the MCP server, so
    that error path is never hit here.
  - The tool's result is returned as a single `TextContent` block whose
    `.text` is `CurrencyConversionResponse.model_dump_json()` — a JSON
    object with keys `from_currency`, `to_currency`, `amount`,
    `converted_amount`, `exchange_rate`, `rate_date` (ISO date string). This
    module parses that JSON into a typed dict instead of returning the raw
    text blob.
"""
from __future__ import annotations

import asyncio
import json
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
        return {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "amount": amount,
            "converted_amount": amount,
            "exchange_rate": 1.0,
            "rate_date": None,
        }
    try:
        raw_text = asyncio.run(_convert_async(amount, from_currency, to_currency))
    except FxRateError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FxRateError(f"Frankfurter MCP call failed for {from_currency}->{to_currency}: {exc}") from exc
    try:
        payload = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise FxRateError(
            f"Frankfurter MCP returned unparseable JSON for {from_currency}->{to_currency}: {raw_text!r}"
        ) from exc
    try:
        return {
            "from_currency": payload["from_currency"],
            "to_currency": payload["to_currency"],
            "amount": payload["amount"],
            "converted_amount": payload["converted_amount"],
            "exchange_rate": payload["exchange_rate"],
            "rate_date": payload["rate_date"],
        }
    except KeyError as exc:
        raise FxRateError(
            f"Frankfurter MCP response missing expected field {exc} for {from_currency}->{to_currency}: {payload}"
        ) from exc
