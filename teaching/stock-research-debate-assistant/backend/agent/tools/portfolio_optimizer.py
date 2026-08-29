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
    }


def optimize_portfolio(
    tickers: list[str],
    fetched_data: dict,
    *,
    amount: float = 0.0,
    currency: str = "USD",
    target_return: float | None = None,
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

    def variance(weights):
        return float(weights @ covariance @ weights)

    constraints = [{"type": "eq", "fun": lambda weights: float(weights.sum() - 1)}]
    if target_return is not None:
        constraints.append({"type": "ineq", "fun": lambda weights: float(weights @ annual_returns - target_return)})
    result = minimize(
        variance,
        equal_weights,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * count,
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
        "method": "Long-only minimum-variance optimization",
        "allocation_reasoning": (
            "Weights minimize the covariance-based historical portfolio variance "
            "subject to weights summing to 100% and no short positions. "
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
