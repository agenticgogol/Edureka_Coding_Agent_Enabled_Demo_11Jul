"""Deterministic portfolio analytics and long-only optimization.

This module is deliberately not an LLM tool. Every weight and metric is
computed from the historical close series returned by yfinance.
"""
from __future__ import annotations

from datetime import date

import numpy as np
from scipy.optimize import minimize


class PortfolioOptimizationError(RuntimeError):
    """Raised when historical data cannot support a valid optimization."""


def _price_matrix(tickers: list[str], fetched_data: dict) -> tuple[list[str], np.ndarray]:
    series = {}
    for ticker in tickers:
        payload = (fetched_data.get(ticker) or {}).get("price_fundamentals") or {}
        rows = payload.get("price_history") or []
        prices = {
            row.get("date"): float(row["close"])
            for row in rows
            if row.get("date") and row.get("close") is not None and float(row["close"]) > 0
        }
        if len(prices) < 60:
            raise PortfolioOptimizationError(
                f"{ticker} has insufficient historical close data; at least 60 observations are required."
            )
        series[ticker] = prices
    dates = sorted(set.intersection(*(set(values) for values in series.values())))
    if len(dates) < 60:
        raise PortfolioOptimizationError("The requested tickers do not have 60 common trading dates.")
    matrix = np.array([[series[ticker][day] for ticker in tickers] for day in dates], dtype=float)
    return dates, matrix


def _metrics(weights: np.ndarray, daily_returns: np.ndarray, covariance: np.ndarray) -> dict:
    annual_returns = daily_returns.mean(axis=0) * 252
    portfolio_return = float(weights @ annual_returns)
    portfolio_volatility = float(np.sqrt(max(weights @ covariance @ weights, 0.0)) * np.sqrt(252))
    risk_contribution = (
        weights * (covariance @ weights) * 252 / portfolio_volatility
        if portfolio_volatility > 0
        else np.zeros(len(weights))
    )
    return {
        "historical_annual_returns": annual_returns.tolist(),
        "expected_annual_return": portfolio_return,
        "annualized_volatility": portfolio_volatility,
        "risk_contributions": risk_contribution.tolist(),
        # Hidden-correlation-risk (Phase 2 item 5): expose the covariance
        # matrix itself, not just per-name/sector weights, so a
        # concentration-risk answer can name correlated pairs, not only
        # single-name/sector weight thresholds.
        "covariance_matrix": covariance.tolist(),
    }


def apply_shock(
    tickers: list[str],
    weights: list[float],
    daily_returns: np.ndarray,
    covariance: np.ndarray,
    *,
    shock_ticker: str | None = None,
    return_shift: float = 0.0,
    correlation_to_one: bool = False,
) -> dict:
    """Shock the returns/covariance inputs and recompute `_metrics()` on
    them, for before/after portfolio stress testing.

    - `return_shift`: annualized return shift applied to `shock_ticker`'s
      column of daily_returns (e.g. -0.20 for "tech sector -20%"). Applied
      to every ticker if `shock_ticker` is None (broad market shock).
    - `correlation_to_one`: if True, replaces the covariance matrix's
      off-diagonal correlations with 1.0 (keeping each ticker's own
      variance), simulating a correlation-breakdown stress scenario.
    """
    weights_arr = np.array(weights, dtype=float)
    shocked_returns = daily_returns.copy()
    daily_shift = return_shift / 252
    if shock_ticker is None:
        shocked_returns += daily_shift
    elif shock_ticker in tickers:
        idx = tickers.index(shock_ticker)
        shocked_returns[:, idx] += daily_shift

    shocked_cov = covariance.copy()
    if correlation_to_one:
        std = np.sqrt(np.diag(covariance))
        shocked_cov = np.outer(std, std)

    before = _metrics(weights_arr, daily_returns, covariance)
    after = _metrics(weights_arr, shocked_returns, shocked_cov)
    return {
        "tickers": tickers,
        "shock_ticker": shock_ticker,
        "return_shift": return_shift,
        "correlation_to_one": correlation_to_one,
        "before": before,
        "after": after,
    }


def stress_test_portfolio(
    tickers: list[str],
    weights: list[float],
    fetched_data: dict,
    *,
    shock_ticker: str | None = None,
    return_shift: float = 0.0,
    correlation_to_one: bool = False,
) -> dict:
    """Convenience wrapper: rebuild the returns/covariance matrix for
    `tickers` from `fetched_data` (same source `optimize_portfolio` uses)
    and run `apply_shock` with the given (already-known) weights."""
    normalized = [t.strip().upper() for t in tickers]
    if len(normalized) != len(weights):
        raise PortfolioOptimizationError("tickers and weights must be the same length.")
    _dates, prices = _price_matrix(normalized, fetched_data)
    daily_returns = prices[1:] / prices[:-1] - 1
    covariance = np.atleast_2d(np.cov(daily_returns, rowvar=False))
    return apply_shock(
        normalized, weights, daily_returns, covariance,
        shock_ticker=shock_ticker, return_shift=return_shift, correlation_to_one=correlation_to_one,
    )


def optimize_portfolio(
    tickers: list[str],
    fetched_data: dict,
    *,
    amount: float = 0.0,
    currency: str = "USD",
    target_return: float | None = None,
    risk_tolerance: str = "moderate",
) -> dict:
    """Return optimized and equal-weight allocations from historical prices.

    The return metric is historical annualized arithmetic return, not a
    forecast. With no target, the optimizer minimizes historical variance.
    With a target, it minimizes variance subject to historical return >= the
    requested target. Short positions and leverage are never permitted.
    """
    normalized = list(dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker.strip()))
    if len(normalized) < 2:
        raise PortfolioOptimizationError("Portfolio optimization requires at least two tickers.")
    if amount < 0:
        raise PortfolioOptimizationError("Investment amount cannot be negative.")
    dates, prices = _price_matrix(normalized, fetched_data)
    daily_returns = prices[1:] / prices[:-1] - 1
    covariance = np.atleast_2d(np.cov(daily_returns, rowvar=False))
    annual_returns = daily_returns.mean(axis=0) * 252
    count = len(normalized)
    equal_weights = np.full(count, 1.0 / count)

    profile = risk_tolerance.lower().strip()
    if profile not in {"conservative", "moderate", "aggressive"}:
        profile = "moderate"
    # This is a deterministic policy applied before optimization. It gives
    # conservative and moderate profiles concentration limits while allowing
    # an aggressive profile to favor historical return without inventing
    # weights in the LLM.
    max_weight = {"conservative": 0.50, "moderate": 0.75, "aggressive": 1.0}[profile]

    def objective(weights):
        if profile == "aggressive":
            return -float(weights @ annual_returns)
        return float(weights @ covariance @ weights)

    constraints = [{"type": "eq", "fun": lambda weights: float(weights.sum() - 1)}]
    if target_return is not None:
        constraints.append({"type": "ineq", "fun": lambda weights: float(weights @ annual_returns - target_return)})
    result = minimize(
        objective,
        equal_weights,
        method="SLSQP",
        bounds=[(0.0, max_weight)] * count,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not result.success:
        raise PortfolioOptimizationError(
            f"Could not find a feasible allocation: {result.message}. "
            "Try a lower historical target return."
        )
    weights = np.clip(result.x, 0.0, 1.0)
    weights /= weights.sum()
    optimized_metrics = _metrics(weights, daily_returns, covariance)
    equal_metrics = _metrics(equal_weights, daily_returns, covariance)
    sectors = {
        ticker: ((fetched_data.get(ticker) or {}).get("price_fundamentals") or {}).get("sector") or "Unknown"
        for ticker in normalized
    }
    sector_weights: dict[str, float] = {}
    for ticker, weight in zip(normalized, weights):
        sector_weights[sectors[ticker]] = sector_weights.get(sectors[ticker], 0.0) + float(weight)
    return {
        "as_of": dates[-1],
        "history_start": dates[0],
        "history_end": dates[-1],
        "tickers": normalized,
        "amount": float(amount),
        "currency": currency.upper(),
        "target_return": target_return,
        "risk_tolerance": profile,
        "max_single_weight": max_weight,
        "method": (
            "Long-only minimum-variance optimization with a 50% maximum holding"
            if profile == "conservative"
            else "Long-only minimum-variance optimization with a 75% maximum holding"
            if profile == "moderate"
            else "Long-only historical-return optimization; concentration is permitted"
        ),
        "allocation_reasoning": (
            f"The {profile} profile applies a deterministic {max_weight * 100:.0f}% maximum "
            "to any one holding. "
            + ("Weights minimize historical portfolio variance. " if profile != "aggressive" else "Weights favor the highest historical portfolio return. ")
            + "Weights sum to 100% and short positions are not allowed. "
            "The requested target is enforced as a minimum historical annual return "
            "when supplied."
        ),
        "basis": "Historical daily close data annualized over 252 trading days; not a forecast.",
        "allocations": [
            {
                "ticker": ticker,
                "weight": float(weight),
                "amount": float(amount * weight),
                "historical_return": float(annual_return),
                "risk_contribution": float(risk_contribution),
                "sector": sectors[ticker],
            }
            for ticker, weight, annual_return, risk_contribution in zip(
                normalized,
                weights,
                optimized_metrics["historical_annual_returns"],
                optimized_metrics["risk_contributions"],
            )
        ],
        "optimized": optimized_metrics,
        "equal_weight": {
            "weights": equal_weights.tolist(),
            "allocations": [
                {"ticker": ticker, "weight": float(weight), "amount": float(amount * weight)}
                for ticker, weight in zip(normalized, equal_weights)
            ],
            **equal_metrics,
        },
        "sector_weights": sector_weights,
        "generated_on": date.today().isoformat(),
    }
