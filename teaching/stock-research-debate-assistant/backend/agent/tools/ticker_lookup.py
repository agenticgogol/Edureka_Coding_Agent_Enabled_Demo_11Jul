"""Company-name -> ticker resolution via yfinance's `Search`, for when a
user names a company ("Reliance") rather than a ticker. Complementary to
`check_ticker_exists` in price_fundamentals.py, which validates a symbol
you already have.
"""
from __future__ import annotations

import yfinance as yf

# Re-sort priority: Indian NSE listings first, then BSE, then everything
# else — applied on top of yfinance's own relevance ranking, not instead
# of it (see plan: "do NOT just trust yfinance's own relevance score").
_EXCHANGE_PRIORITY = {"NSE": 0, "BSE": 1}


def _priority(candidate: dict) -> int:
    symbol = (candidate.get("symbol") or "").upper()
    if symbol.endswith(".NS"):
        return 0
    if symbol.endswith(".BO"):
        return 1
    return 2


def resolve_company_name(query: str, max_results: int = 5) -> list[dict]:
    """Return ranked candidates for a free-text company name/query.

    Each candidate: {"symbol": str, "name": str, "exchange": str}.
    Empty list if yfinance's Search finds nothing or errors out.
    """
    query = (query or "").strip()
    if not query:
        return []
    try:
        results = yf.Search(query, max_results=max_results).quotes or []
    except Exception:  # noqa: BLE001
        return []

    candidates = [
        {
            "symbol": item.get("symbol"),
            "name": item.get("shortname") or item.get("longname") or item.get("symbol"),
            "exchange": item.get("exchDisp") or item.get("exchange"),
        }
        for item in results
        if item.get("symbol")
    ]
    # Stable sort preserves yfinance's own relevance order within each
    # exchange-priority bucket.
    candidates.sort(key=_priority)
    return candidates
