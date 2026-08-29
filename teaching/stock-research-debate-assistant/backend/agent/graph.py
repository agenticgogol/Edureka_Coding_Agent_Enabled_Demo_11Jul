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
         -> judge -> END

No checkpointer is used here: `run_turn` (see __init__.py) is invoked once
per HTTP chat turn with the previous turn's full state as input, and
GraphState's reducers (see state.py) handle correctly accumulating
transcript/trail and merging fetched_data across turns without needing
LangGraph's own persistence layer. There is no human-in-the-loop
interrupt/resume requirement in this design (Q2 = No, no HITL needed).
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .nodes.debate import run_debate, run_risk_refine
from .nodes.fetch import fetch_fx_node, fetch_news_node, fetch_price_node, skip_news_node
from .nodes.judge import run_judge
from .nodes.light_answers import answer_drill_down, answer_follow_up, decline, invalid_ticker
from .nodes.orchestrator import route
from .state import GraphState

_FRESH_PIPELINE_TURN_TYPES = {"new_analysis", "topic_switch", "comparison"}


def _route_after_orchestrator(state: GraphState):
    turn_type = state.get("turn_type")

    if turn_type == "out_of_scope":
        return "decline"
    if turn_type == "drill_down":
        return "drill_down_answer"
    if turn_type == "follow_up":
        return "follow_up_answer"
    if turn_type == "refinement":
        return "risk_refine"

    if turn_type in _FRESH_PIPELINE_TURN_TYPES:
        tickers = state.get("tickers", [])
        if not tickers:
            return "invalid_ticker"
        selected_tools = state.get("selected_tools", [])
        sends: list[Send] = []
        for ticker in tickers:
            sends.append(Send("fetch_price", {**state, "_fetch_ticker": ticker}))
            if "news" in selected_tools:
                sends.append(Send("fetch_news", {**state, "_fetch_ticker": ticker}))
        if "news" not in selected_tools:
            sends.append(Send("skip_news", state))
        return sends

    # Defensive fallback: an unrecognized turn_type is treated as a fresh
    # analysis attempt rather than silently dropping the turn.
    return "invalid_ticker" if not state.get("tickers") else [Send("fetch_price", {**state, "_fetch_ticker": t}) for t in state["tickers"]]


def build_graph():
    workflow = StateGraph(GraphState)

    workflow.add_node("orchestrator", route)
    workflow.add_node("fetch_price", fetch_price_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("skip_news", skip_news_node)
    workflow.add_node("fetch_fx", fetch_fx_node)
    workflow.add_node("debate", run_debate)
    workflow.add_node("risk_refine", run_risk_refine)
    workflow.add_node("judge", run_judge)
    workflow.add_node("drill_down_answer", answer_drill_down)
    workflow.add_node("follow_up_answer", answer_follow_up)
    workflow.add_node("decline", decline)
    workflow.add_node("invalid_ticker", invalid_ticker)

    workflow.add_edge(START, "orchestrator")
    workflow.add_conditional_edges("orchestrator", _route_after_orchestrator)

    # Join barrier: every fan-out branch converges here before FX runs.
    workflow.add_edge("fetch_price", "fetch_fx")
    workflow.add_edge("fetch_news", "fetch_fx")
    workflow.add_edge("skip_news", "fetch_fx")

    workflow.add_edge("fetch_fx", "debate")
    workflow.add_edge("debate", "judge")
    workflow.add_edge("risk_refine", "judge")

    workflow.add_edge("judge", END)
    workflow.add_edge("drill_down_answer", END)
    workflow.add_edge("follow_up_answer", END)
    workflow.add_edge("decline", END)
    workflow.add_edge("invalid_ticker", END)

    return workflow.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
