"""Reverse single-stage DCF: given current market cap and free cash flow,
root-solve the perpetual growth rate that the market is implicitly pricing
in. Deliberately simplified — a single-stage Gordon-growth model, not a
multi-stage/precision valuation — callers must present it as illustrative.
"""
from __future__ import annotations

DEFAULT_DISCOUNT_RATE = 0.10


class ReverseDCFError(RuntimeError):
    """Raised when the inputs can't support a reverse-DCF solve."""


def implied_growth_rate(
    market_cap: float,
    free_cashflow: float,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> dict:
    """Solve g in: market_cap = fcf * (1 + g) / (discount_rate - g).

    Single-stage Gordon growth model, closed-form (no numerical solver
    needed): g = (discount_rate * market_cap - fcf) / (market_cap + fcf).
    """
    if not market_cap or market_cap <= 0:
        raise ReverseDCFError("Market cap is missing or non-positive; cannot solve implied growth.")
    if not free_cashflow or free_cashflow <= 0:
        raise ReverseDCFError("Free cash flow is missing or non-positive; reverse DCF requires positive FCF.")

    implied_g = (discount_rate * market_cap - free_cashflow) / (market_cap + free_cashflow)
    if implied_g >= discount_rate:
        raise ReverseDCFError(
            "Implied growth rate would exceed the discount rate — the single-stage model is "
            "not valid for this price/FCF combination."
        )
    return {
        "discount_rate": discount_rate,
        "implied_growth_rate": implied_g,
        "market_cap": market_cap,
        "free_cashflow": free_cashflow,
        "model": "single-stage Gordon growth reverse DCF (simplified, illustrative — not precision finance)",
    }
