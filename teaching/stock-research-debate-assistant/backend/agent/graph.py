"""LangGraph graph assembly: supervisor-specialists multi-agent topology
combining fan-out data-gathering with adversarial-debate synthesis.

Topology:
  START -> orchestrator
    -> [out_of_scope]      -> decline -> END
    -> [no ticker resolved] -> invalid_ticker -> END
    -> [drill_down]         -> drill_down_answer -> END
    -> [follow_up]          -> follow_up_answer -> END
    -> [refinement]         -> risk_refine -> judge -> END
    -> [new_analysis / topic_switch / comparison]
         -> Send-based fan-out: fetch_price (per ticker, always) and
            fetch_news (per ticker, only if selected) or skip_news
         -> (join barrier) -> fetch_fx (derives currency pair from what
            fetch_price actually returned; skips itself if not needed)
         -> debate (bounded 2-round bull/bear/risk)
         -> judge
              -> [judge's bull/bear agreement confidence < 0.35, i.e.
                  sharp/unresolved conflict, on this same fresh turn,
                  and no extra round has run yet this turn]
                    -> debate_extra_round (one more bull/bear rebuttal
                       round, capped: never loops twice) -> judge (again)
              -> [else] -> END

No checkpointer is used here: `run_turn` (see __init__.py) is invoked once
per HTTP chat turn with the previous turn's full state as input, and
GraphState's reducers (see state.py) handle correctly accumulating
transcript/trail and merging fetched_data across turns without needing
LangGraph's own persistence layer. There is no human-in-the-loop
interrupt/resume requirement in this design (Q2 = No, no HITL needed).
"""
from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .nodes.debate import run_debate, run_extra_round, run_risk_refine
from .nodes.fetch import fetch_fx_node, fetch_news_node, fetch_price_node, skip_news_node
from .nodes.judge import CONFLICT_CONFIDENCE_THRESHOLD, run_judge
from .nodes.light_answers import (
    answer_allocation,
    answer_critique,
    answer_drill_down,
    answer_follow_up,
    answer_news_materiality,
    answer_price_move,
    answer_quick_summary,
    answer_reverse_dcf,
    answer_scenarios,
    decline,
    invalid_ticker,
)
from .nodes.orchestrator import route
from .nodes.portfolio import optimize_node, stress_test_node
from .state import GraphState

_FRESH_PIPELINE_TURN_TYPES = {"new_analysis", "topic_switch", "comparison"}
_ALLOCATION_FETCH_TURN_TYPES = {"allocation_new", "allocation_list_change"}
_QUICK_SUMMARY_TURN_TYPES = {"quick_summary"}
# reverse_dcf needs price/fundamentals fetched (market cap + FCF) for its
# ticker but, like quick_summary, skips news/fx/debate — same fan-out shape.
_PRICE_ONLY_TURN_TYPES = {"quick_summary", "reverse_dcf"}

# How long a cached `fetched_data[ticker]["price_fundamentals"]` entry is
# considered fresh enough to reuse without re-fetching. Ties into the
# short-TTL caching layer added for price/fundamentals data (see fetch.py's
# "fetched_at" timestamp) — same freshness window used by both the
# allocation fetch path and the fresh-analysis fan-out below, so a ticker
# already fetched this session isn't refetched on every turn.
_DATA_FRESH_SECONDS = 10 * 60


def _has_fresh_price_data(existing: dict, ticker: str) -> bool:
    entry = (existing.get(ticker) or {}).get("price_fundamentals")
    if not entry:
        return False
    fetched_at = entry.get("fetched_at")
    if fetched_at is None:
        # Data fetched before this freshness field existed (or the news
        # sub-fetch already ran without prices) — treat as stale rather
        # than trusting it indefinitely.
        return False
    return (time.time() - fetched_at) < _DATA_FRESH_SECONDS


def _route_after_orchestrator(state: GraphState):
    turn_type = state.get("turn_type")

    if turn_type == "out_of_scope":
        return "decline"
    if turn_type == "drill_down":
        return "drill_down_answer"
    if turn_type == "follow_up":
        return "follow_up_answer"
    if turn_type == "critique":
        return "critique_answer"
    if turn_type == "price_move_explain":
        return "price_move_explain_answer"
    if turn_type == "scenario_simulator":
        return "scenario_simulator_answer"
    if turn_type == "news_materiality":
        return "news_materiality_answer"
    if turn_type in {"allocation_compare", "allocation_drill_down"}:
        return "allocation_answer"
    if turn_type == "portfolio_stress_test":
        return "portfolio_stress_test_answer"
    if turn_type == "refinement":
        return "risk_refine"

    if (
        turn_type in _ALLOCATION_FETCH_TURN_TYPES
        or turn_type in _FRESH_PIPELINE_TURN_TYPES
        or turn_type in _PRICE_ONLY_TURN_TYPES
    ):
        tickers = state.get("tickers", [])
        if not tickers:
            return "invalid_ticker"
        # quick_summary/reverse_dcf skip news/fx for speed/cost — price only.
        selected_tools = [] if turn_type in _PRICE_ONLY_TURN_TYPES else state.get("selected_tools", [])
        sends: list[Send] = []
        existing = state.get("fetched_data", {})
        for ticker in tickers:
            if _has_fresh_price_data(existing, ticker):
                continue
            sends.append(Send("fetch_price", {**state, "_fetch_ticker": ticker}))
            if "news" in selected_tools:
                sends.append(Send("fetch_news", {**state, "_fetch_ticker": ticker}))
        if "news" not in selected_tools and turn_type not in _ALLOCATION_FETCH_TURN_TYPES:
            sends.append(Send("skip_news", state))
        if not sends:
            # Every requested ticker already had fresh cached data (and,
            # for the non-allocation path, news wasn't requested either
            # so skip_news would normally have been appended) — nothing
            # left to fan out, so go straight to the join-barrier node.
            return "fetch_fx"
        return sends

    if turn_type == "allocation_parameter_change":
        return "optimizer"

    # Defensive fallback: an unrecognized turn_type is treated as a fresh
    # analysis attempt rather than silently dropping the turn.
    return "invalid_ticker" if not state.get("tickers") else [Send("fetch_price", {**state, "_fetch_ticker": t}) for t in state["tickers"]]


def _route_after_judge(state: GraphState):
    """Adaptive debate depth (see nodes/debate.py's `run_extra_round` and
    nodes/judge.py's `CONFLICT_CONFIDENCE_THRESHOLD` docstrings for the
    full rationale). Only fires for a fresh stock-analysis turn (not
    allocation, not a refinement re-judge) whose judge-estimated bull/bear
    agreement is below threshold, and only once per turn (`debate_extended`
    guards against looping)."""
    confidence = state.get("confidence")
    turn_type = state.get("turn_type")
    sharply_conflicting = confidence is not None and confidence < CONFLICT_CONFIDENCE_THRESHOLD
    if (
        sharply_conflicting
        and turn_type in _FRESH_PIPELINE_TURN_TYPES
        and not state.get("allocation_output")
        and not state.get("debate_extended")
    ):
        return "debate_extra_round"
    return END


def build_graph():
    workflow = StateGraph(GraphState)

    workflow.add_node("orchestrator", route)
    workflow.add_node("fetch_price", fetch_price_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("skip_news", skip_news_node)
    workflow.add_node("fetch_fx", fetch_fx_node)
    workflow.add_node("debate", run_debate)
    workflow.add_node("debate_extra_round", run_extra_round)
    workflow.add_node("optimizer", optimize_node)
    workflow.add_node("risk_refine", run_risk_refine)
    workflow.add_node("judge", run_judge)
    workflow.add_node("drill_down_answer", answer_drill_down)
    workflow.add_node("follow_up_answer", answer_follow_up)
    workflow.add_node("quick_summary_answer", answer_quick_summary)
    workflow.add_node("critique_answer", answer_critique)
    workflow.add_node("price_move_explain_answer", answer_price_move)
    workflow.add_node("scenario_simulator_answer", answer_scenarios)
    workflow.add_node("news_materiality_answer", answer_news_materiality)
    workflow.add_node("reverse_dcf_answer", answer_reverse_dcf)
    workflow.add_node("allocation_answer", answer_allocation)
    workflow.add_node("portfolio_stress_test_answer", stress_test_node)
    workflow.add_node("decline", decline)
    workflow.add_node("invalid_ticker", invalid_ticker)

    workflow.add_edge(START, "orchestrator")
    workflow.add_conditional_edges("orchestrator", _route_after_orchestrator)

    # Join barrier: every fan-out branch converges here before FX runs.
    workflow.add_edge("fetch_price", "fetch_fx")
    workflow.add_edge("fetch_news", "fetch_fx")
    workflow.add_edge("skip_news", "fetch_fx")

    workflow.add_conditional_edges(
        "fetch_fx",
        lambda state: (
            "optimizer" if state.get("allocation_requested")
            else "quick_summary_answer" if state.get("turn_type") == "quick_summary"
            else "reverse_dcf_answer" if state.get("turn_type") == "reverse_dcf"
            else "debate"
        ),
    )
    workflow.add_conditional_edges("optimizer", lambda state: "debate" if state.get("allocation_output") else END)
    workflow.add_edge("debate", "judge")
    workflow.add_edge("risk_refine", "judge")
    workflow.add_edge("debate_extra_round", "judge")

    workflow.add_conditional_edges("judge", _route_after_judge)
    workflow.add_edge("drill_down_answer", END)
    workflow.add_edge("follow_up_answer", END)
    workflow.add_edge("quick_summary_answer", END)
    workflow.add_edge("critique_answer", END)
    workflow.add_edge("price_move_explain_answer", END)
    workflow.add_edge("scenario_simulator_answer", END)
    workflow.add_edge("news_materiality_answer", END)
    workflow.add_edge("reverse_dcf_answer", END)
    workflow.add_edge("allocation_answer", END)
    workflow.add_edge("portfolio_stress_test_answer", END)
    workflow.add_edge("decline", END)
    workflow.add_edge("invalid_ticker", END)

    return workflow.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
