"""Direct yfinance call (NOT MCP) — price, key fundamentals, and recent
price history for a US or Indian ticker.

Per architecture_design.md: ticker validity is folded into this fetch —
an invalid/unknown ticker returns no usable data, which the caller (the
orchestrator/fetch node) treats as invalid rather than a separate lookup.
"""
from __future__ import annotations

import yfinance as yf

# Curated, hand-maintained peer map for a small set of well-known large-cap
# tickers. Not live discovery — no yfinance/installed-dependency API exposes
# a peer/sector reverse lookup (confirmed during Phase 2 planning). Used only
# to suggest peers when the user asks to compare a ticker to "its peers"
# without naming a second ticker; always label output as curated, not live,
# wherever this surfaces.
PEER_MAP: dict[str, list[str]] = {
    "AAPL": ["MSFT", "GOOGL"],
    "MSFT": ["AAPL", "GOOGL"],
    "GOOGL": ["MSFT", "META"],
    "GOOG": ["MSFT", "META"],
    "META": ["GOOGL", "SNAP"],
    "AMZN": ["WMT", "SHOP"],
    "TSLA": ["F", "GM"],
    "NVDA": ["AMD", "INTC"],
    "AMD": ["NVDA", "INTC"],
    "INTC": ["AMD", "NVDA"],
    "NFLX": ["DIS", "CMCSA"],
    "DIS": ["NFLX", "CMCSA"],
    "JPM": ["BAC", "WFC"],
    "BAC": ["JPM", "WFC"],
    "WFC": ["JPM", "BAC"],
    "GS": ["MS", "JPM"],
    "MS": ["GS", "JPM"],
    "V": ["MA", "AXP"],
    "MA": ["V", "AXP"],
    "KO": ["PEP"],
    "PEP": ["KO"],
    "WMT": ["TGT", "COST"],
    "TGT": ["WMT", "COST"],
    "COST": ["WMT", "TGT"],
    "XOM": ["CVX"],
    "CVX": ["XOM"],
    "PFE": ["JNJ", "MRK"],
    "JNJ": ["PFE", "MRK"],
    "MRK": ["PFE", "JNJ"],
    "TCS.NS": ["INFY.NS", "WIPRO.NS"],
    "INFY.NS": ["TCS.NS", "WIPRO.NS"],
    "RELIANCE.NS": ["TCS.NS", "INFY.NS"],
}


class TickerNotFoundError(RuntimeError):
    """Raised when yfinance returns no usable price/fundamentals data."""


def check_ticker_exists(ticker: str) -> dict:
    """Cheap, non-LLM ticker-existence check for the `/tickers/validate` API
    endpoint, so the frontend can reject a bad ticker before spending a
    full paid `/chat` turn on it.

    Deliberately lighter than `fetch_price_fundamentals` above: uses
    yfinance's `fast_info` (a much cheaper quote-only lookup) first, and
    only falls back to a short 5-day history call if `fast_info` doesn't
    resolve a price — never calls the expensive `.info` fundamentals
    lookup, since this endpoint only needs to answer "does this symbol
    exist," not fetch fundamentals.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        return {"symbol": symbol, "valid": False, "detail": "empty ticker symbol"}

    ticker_obj = yf.Ticker(symbol)
    try:
        fast = ticker_obj.fast_info
        last_price = fast.get("lastPrice") if fast else None
    except Exception:  # noqa: BLE001
        last_price = None

    if last_price:
        return {"symbol": symbol, "valid": True, "detail": None}

    try:
        history = ticker_obj.history(period="5d")
    except Exception as exc:  # noqa: BLE001
        return {"symbol": symbol, "valid": False, "detail": f"lookup failed: {exc}"}

    if history.empty:
        return {"symbol": symbol, "valid": False, "detail": "no price data found for this symbol"}
    return {"symbol": symbol, "valid": True, "detail": None}


def _serialize_financial_statement(df) -> dict:
    """Transpose a yfinance financials/balance_sheet/cashflow DataFrame
    (line-item rows x period columns) to {period_end_date_str: {line_item:
    value_or_None}}, matching the NaN-handling pattern used for
    `price_history` above (`value == value` is False for NaN)."""
    if df is None or df.empty:
        return {}
    return {
        str(period.date()) if hasattr(period, "date") else str(period): {
            str(line_item): float(value) if value == value else None
            for line_item, value in column.items()
        }
        for period, column in df.items()
    }


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

    income_statement = _serialize_financial_statement(ticker_obj.financials)
    balance_sheet = _serialize_financial_statement(ticker_obj.balance_sheet)
    cashflow_statement = _serialize_financial_statement(ticker_obj.cashflow)

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    market_cap = info.get("marketCap")
    free_cashflow = info.get("freeCashflow")
    fcf_yield = (
        free_cashflow / market_cap if isinstance(free_cashflow, (int, float)) and isinstance(market_cap, (int, float)) and market_cap else None
    )
    return {
        "ticker": symbol,
        "currency": info.get("currency"),
        "current_price": current_price,
        "market_cap": market_cap,
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
        # Valuation (A2)
        "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
        "price_to_sales_trailing_12_months": info.get("priceToSalesTrailing12Months"),
        "free_cashflow": free_cashflow,
        "fcf_yield": fcf_yield,
        # Growth/profitability/debt/cashflow (A3)
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "return_on_equity": info.get("returnOnEquity"),
        "operating_margins": info.get("operatingMargins"),
        "operating_cashflow": info.get("operatingCashflow"),
        # Dividend (A8)
        "payout_ratio": info.get("payoutRatio"),
        "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield"),
        "dividend_rate": info.get("dividendRate"),
        "ex_dividend_date": info.get("exDividendDate"),
        # Analyst ratings/target prices (Phase 2 item 1) — same .info call
        # already made above, previously-unused fields.
        "target_mean_price": info.get("targetMeanPrice"),
        "target_high_price": info.get("targetHighPrice"),
        "target_low_price": info.get("targetLowPrice"),
        "recommendation_key": info.get("recommendationKey"),
        "price_history": price_history,
        # Financial statements (Phase 3 item 1) — each is
        # {period_end_date_str: {line_item: value_or_None}}.
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cashflow_statement": cashflow_statement,
    }
