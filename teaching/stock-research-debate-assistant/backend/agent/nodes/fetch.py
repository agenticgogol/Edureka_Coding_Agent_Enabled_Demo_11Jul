"""Fan-out data-fetch node functions. Each is invoked once per (ticker,
tool) pair the orchestrator selected, via `langgraph.types.Send` from
`graph.py`'s conditional edge — so multiple fetches for multiple tickers
or tools genuinely run as separate graph steps that fan back in at the
debate node.
"""
from __future__ import annotations

import time

from ..state import GraphState, emit_progress
from ..tools.fx_rate import FxRateError, fetch_fx_rate
from ..tools.news_search import NewsSearchError, fetch_news
from ..tools.price_fundamentals import TickerNotFoundError, fetch_price_fundamentals


def fetch_price_node(state: GraphState) -> dict:
    ticker = state["_fetch_ticker"]
    emit_progress(state, "fetch_price_fundamentals", "started", "Fetching historical price and fundamentals", ticker)
    try:
        data = fetch_price_fundamentals(ticker)
        data["fetched_at"] = time.time()
        emit_progress(state, "fetch_price_fundamentals", "done", "Price and fundamentals loaded", ticker)
        return {
            "fetched_data": {ticker: {"price_fundamentals": data}},
            "trail": [{"step": "fetch_price_fundamentals", "ticker": ticker, "status": "done", "detail": data}],
        }
    except TickerNotFoundError as exc:
        emit_progress(state, "fetch_price_fundamentals", "error", str(exc), ticker)
        return {
            "fetched_data": {ticker: {"price_fundamentals": None, "error": str(exc)}},
            "trail": [{"step": "fetch_price_fundamentals", "ticker": ticker, "status": "error", "detail": str(exc)}],
        }


def fetch_news_node(state: GraphState) -> dict:
    ticker = state["_fetch_ticker"]
    emit_progress(state, "fetch_news", "started", "Searching recent news", ticker)
    try:
        data = fetch_news(ticker)
        emit_progress(state, "fetch_news", "done", "Recent news loaded", ticker)
        return {
            "fetched_data": {ticker: {"news": data}},
            "trail": [{"step": "fetch_news", "ticker": ticker, "status": "done", "detail": data}],
        }
    except NewsSearchError as exc:
        emit_progress(state, "fetch_news", "error", str(exc), ticker)
        return {
            "fetched_data": {ticker: {"news": None, "error": str(exc)}},
            "trail": [{"step": "fetch_news", "ticker": ticker, "status": "error", "detail": str(exc)}],
        }


def fetch_fx_node(state: GraphState) -> dict:
    """Runs AFTER the price fan-out converges (see graph.py) so it can
    read the currencies yfinance actually returned per ticker, rather
    than guessing a currency pair up front."""
    emit_progress(state, "fetch_fx", "started", "Checking whether currency conversion is needed")
    if not state.get("needs_fx"):
        emit_progress(state, "fetch_fx", "skipped", "No cross-currency comparison needed")
        result = skip_fx_node(state)
        return _comparison_event(state, result)

    currencies: set[str] = set()
    for ticker in state.get("tickers", []):
        price_info = (state.get("fetched_data", {}).get(ticker) or {}).get("price_fundamentals")
        if price_info and price_info.get("currency"):
            currencies.add(price_info["currency"])

    if len(currencies) < 2:
        emit_progress(state, "fetch_fx", "skipped", "Only one currency was found")
        result = {"trail": [{"step": "fetch_fx", "ticker": None, "status": "skipped", "detail": f"only one currency in play: {currencies or 'unknown'}"}]}
        return _comparison_event(state, result)

    from_ccy, to_ccy = sorted(currencies)[:2]
    try:
        data = fetch_fx_rate(from_ccy, to_ccy)
        emit_progress(state, "fetch_fx", "done", f"Converted {from_ccy} to {to_ccy}")
        result = {
            "fx_data": {f"{from_ccy}_{to_ccy}": data},
            "trail": [{"step": "fetch_fx", "ticker": None, "status": "done", "detail": f"{from_ccy}->{to_ccy}"}],
        }
        return _comparison_event(state, result)
    except FxRateError as exc:
        emit_progress(state, "fetch_fx", "error", str(exc))
        result = {
            "fx_data": {f"{from_ccy}_{to_ccy}": {"error": str(exc)}},
            "trail": [{"step": "fetch_fx", "ticker": None, "status": "error", "detail": str(exc)}],
        }
        return _comparison_event(state, result)


def _comparison_event(state: GraphState, result: dict) -> dict:
    """Add one UI-ready comparison payload after parallel price fetches join."""
    tickers = state.get("tickers", [])
    if len(tickers) >= 2:
        result.setdefault("trail", []).append(
            {
                "step": "fundamentals_comparison",
                "ticker": None,
                "status": "done",
                "detail": {
                    "tickers": {
                        ticker: state.get("fetched_data", {}).get(ticker, {}).get("price_fundamentals") or {}
                        for ticker in tickers
                    }
                },
            }
        )
    return result


def skip_news_node(state: GraphState) -> dict:
    """Explicit no-op so the reasoning trail shows news as SKIPPED, not
    silently absent, when the orchestrator decided the question doesn't
    need it (per the happy-path test case's requirement)."""
    emit_progress(state, "fetch_news", "skipped", "Question does not need news")
    return {"trail": [{"step": "fetch_news", "ticker": None, "status": "skipped", "detail": "orchestrator determined this question does not need news"}]}


def skip_fx_node(state: GraphState) -> dict:
    emit_progress(state, "fetch_fx", "skipped", "No cross-currency comparison needed")
    return {"trail": [{"step": "fetch_fx", "ticker": None, "status": "skipped", "detail": "no cross-currency comparison needed"}]}
