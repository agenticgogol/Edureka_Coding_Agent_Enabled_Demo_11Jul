"""Graph node for deterministic portfolio optimization."""
from __future__ import annotations

from ..state import GraphState, emit_progress
from ..tools.portfolio_optimizer import PortfolioOptimizationError, optimize_portfolio


def optimize_node(state: GraphState) -> dict:
    emit_progress(state, "portfolio_optimization", "started", "Computing deterministic historical weights")
    try:
        output = optimize_portfolio(
            state.get("tickers", []),
            state.get("fetched_data", {}),
            amount=state.get("allocation_amount") or 0.0,
            currency=state.get("allocation_currency") or "USD",
            target_return=state.get("allocation_target_return"),
        )
        emit_progress(state, "portfolio_optimization", "done", "Weights, return, volatility, and risk contributions computed")
        allocations = " / ".join(
            f"{item['ticker']} {item['weight'] * 100:.1f}%"
            for item in output["allocations"]
        )
        return {
            "allocation_output": output,
            "trail": [
                {"step": "portfolio_optimization", "ticker": None, "status": "done", "detail": output},
                {"step": "allocation_result", "ticker": None, "status": "done", "detail": f"Historical minimum-variance allocation: {allocations}"},
            ],
        }
    except PortfolioOptimizationError as exc:
        emit_progress(state, "portfolio_optimization", "error", str(exc))
        return {
            "trail": [{"step": "portfolio_optimization", "ticker": None, "status": "error", "detail": str(exc)}],
            "final_answer": f"I could not compute a valid historical allocation: {exc}",
        }
