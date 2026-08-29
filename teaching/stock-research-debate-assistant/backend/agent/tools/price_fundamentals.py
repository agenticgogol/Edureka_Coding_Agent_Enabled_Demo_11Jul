"""Direct yfinance call (NOT MCP) — price, key fundamentals, and recent
price history for a US or Indian ticker.

Per architecture_design.md: ticker validity is folded into this fetch —
an invalid/unknown ticker returns no usable data, which the caller (the
orchestrator/fetch node) treats as invalid rather than a separate lookup.
"""
from __future__ import annotations

import yfinance as yf


class TickerNotFoundError(RuntimeError):
    """Raised when yfinance returns no usable price/fundamentals data."""


def fetch_price_fundamentals(ticker: str, history_period: str = "5y", history_interval: str = "1d") -> dict:
    """Fetch price, fundamentals, and OHLC history for one ticker.

    `ticker` is used as given (e.g. "AAPL", "RELIANCE.NS", "TCS.BO") —
    Indian exchange suffixes are yfinance-native, no separate handling
    needed.
    """
    symbol = ticker.strip().upper()
    ticker_obj = yf.Ticker(symbol)

    try:
        info = ticker_obj.info or {}
    except Exception as exc:  # noqa: BLE001
        raise TickerNotFoundError(f"Could not fetch data for '{symbol}': {exc}") from exc

    history = ticker_obj.history(period=history_period, interval=history_interval)
    if history.empty and not info.get("currentPrice") and not info.get("regularMarketPrice"):
        raise TickerNotFoundError(
            f"'{symbol}' returned no price data — likely an invalid or unrecognized ticker."
        )

    price_history = [
        {
            "date": str(index.date()),
            "open": round(float(row["Open"]), 2) if row["Open"] == row["Open"] else None,
            "close": round(float(row["Close"]), 2) if row["Close"] == row["Close"] else None,
            "high": round(float(row["High"]), 2) if row["High"] == row["High"] else None,
            "low": round(float(row["Low"]), 2) if row["Low"] == row["Low"] else None,
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else None,
        }
        for index, row in history.iterrows()
    ]

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    return {
        "ticker": symbol,
        "currency": info.get("currency"),
        "current_price": current_price,
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margins": info.get("profitMargins"),
        "dividend_yield": info.get("dividendYield"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "long_name": info.get("longName") or info.get("shortName"),
        "price_history": price_history,
    }
