"""Graph node for deterministic portfolio optimization."""
from __future__ import annotations

from ..state import GraphState, emit_progress
from ..tools.portfolio_optimizer import PortfolioOptimizationError, optimize_portfolio, stress_test_portfolio


def optimize_node(state: GraphState) -> dict:
    emit_progress(state, "portfolio_optimization", "started", "Computing deterministic historical weights")
    try:
        output = optimize_portfolio(
            state.get("tickers", []),
            state.get("fetched_data", {}),
            amount=state.get("allocation_amount") or 0.0,
            currency=state.get("allocation_currency") or "USD",
            target_return=state.get("allocation_target_return"),
            risk_tolerance=state.get("risk_tolerance") or "moderate",
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
                {"step": "allocation_result", "ticker": None, "status": "done", "detail": f"{output['risk_tolerance'].title()} profile allocation: {allocations}"},
            ],
        }
    except PortfolioOptimizationError as exc:
        emit_progress(state, "portfolio_optimization", "error", str(exc))
        return {
            "trail": [{"step": "portfolio_optimization", "ticker": None, "status": "error", "detail": str(exc)}],
            "final_answer": f"I could not compute a valid historical allocation: {exc}",
        }


def stress_test_node(state: GraphState) -> dict:
    """Applies a shock to the EXISTING allocation's weights (no
    re-optimization) and reports before/after risk/return via
    `_metrics()`, reused as-is from portfolio_optimizer.py."""
    emit_progress(state, "portfolio_stress_test", "started", "Applying shock to existing allocation")
    output = state.get("allocation_output") or {}
    if not output:
        return {
            "final_answer": "There is no computed allocation in this session yet to stress-test. Ask for an allocation first.",
            "trail": [{"step": "portfolio_stress_test", "ticker": None, "status": "error", "detail": "no allocation_output in state"}],
        }
    tickers = output.get("tickers") or []
    weights = [row["weight"] for row in output.get("allocations", [])]
    try:
        result = stress_test_portfolio(
            tickers,
            weights,
            state.get("fetched_data", {}),
            shock_ticker=state.get("shock_ticker"),
            return_shift=state.get("shock_return_shift") or 0.0,
            correlation_to_one=bool(state.get("shock_correlation_to_one")),
        )
        emit_progress(state, "portfolio_stress_test", "done", "Before/after risk-return computed")
        return {
            "final_answer": (
                f"Stress test — before: return {result['before']['expected_annual_return']:.2%}, "
                f"volatility {result['before']['annualized_volatility']:.2%}. "
                f"After: return {result['after']['expected_annual_return']:.2%}, "
                f"volatility {result['after']['annualized_volatility']:.2%}."
            ),
            "trail": [{"step": "portfolio_stress_test", "ticker": None, "status": "done", "detail": result}],
        }
    except PortfolioOptimizationError as exc:
        emit_progress(state, "portfolio_stress_test", "error", str(exc))
        return {
            "trail": [{"step": "portfolio_stress_test", "ticker": None, "status": "error", "detail": str(exc)}],
            "final_answer": f"I could not run the stress test: {exc}",
        }
