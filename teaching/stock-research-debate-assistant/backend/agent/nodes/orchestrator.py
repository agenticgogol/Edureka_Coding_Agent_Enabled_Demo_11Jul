"""Orchestrator/router node: classifies turn type, resolves ticker(s),
picks which fetch tools this question actually needs, and screens for the
explicit non-goal categories (out-of-scope), per architecture_design.md.

One LLM call via llm_client.complete().
"""
from __future__ import annotations

import json
import re

from ..llm_client import complete
from ..state import GraphState

_SYSTEM_PROMPT = """You are the routing brain for a stock-research debate assistant. \
Given the user's latest message, prior context (previous tickers, whether data was \
already fetched, and the debate transcript so far), classify the turn and decide what \
to do next.

Turn types (pick exactly one):
- "new_analysis": a first-time request to analyze one stock, no prior context needed.
- "topic_switch": the user pivots to a different stock/topic mid-conversation.
- "comparison": the user wants two (or more) tickers compared against each other.
- "follow_up": a question about the SAME already-analyzed ticker(s) that needs the \
already-fetched data (and possibly a short new LLM answer) but does NOT require \
re-fetching data or re-running the full debate.
- "drill_down": a question about WHY an agent (bull/bear/risk/judge) said something \
already in the transcript — answerable purely by reading the transcript, zero new data.
- "refinement": the user states or changes a preference that should change the \
synthesis without new data or a new bull/bear debate — e.g. a stated risk tolerance, \
investment horizon, or "assume a 5-year horizon" — this should re-run only the risk \
assessment and judge synthesis.
- "out_of_scope": the request falls into one of these explicit non-goal categories: \
mutual funds, market timing / short-term price prediction, options / derivatives / \
leverage, portfolio allocation or optimization across multiple tickers, or real \
trading / brokerage actions (e.g. "place this trade for me"). Comparing two SPECIFIC \
stocks the user names is NOT portfolio optimization and is NOT out of scope — only \
classify out_of_scope when the request matches one of these categories, not merely \
because it mentions money or stocks.

Tool selection (pick zero or more from ["price_fundamentals", "news", "fx"]), only \
relevant for new_analysis / topic_switch / comparison:
- "price_fundamentals": needed for almost any real ticker question.
- "news": needed only if the question is news/sentiment/event driven, NOT for a pure \
valuation/fundamentals-only question (e.g. "is MSFT overvalued based on P/E" does not \
need news).
- "fx": needed only for a comparison whose tickers trade in different currencies \
(e.g. one US ticker vs one Indian ticker) and the user needs a common-currency view.

Extract ticker symbols exactly as the user would type them into yfinance (e.g. AAPL, \
MSFT, RELIANCE.NS, TCS.NS, INFY.BO). For follow_up/drill_down/refinement, resolve \
pronouns ("it", "that stock") to the ticker(s) already in context.

Respond with ONLY a JSON object, no prose, no markdown fences:
{
  "turn_type": "...",
  "tickers": ["..."],
  "selected_tools": ["..."],
  "needs_fx": true/false,
  "out_of_scope_reason": "..." or null,
  "notes": "one short sentence explaining the classification"
}
"""


def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def route(state: GraphState) -> dict:
    prior_tickers = state.get("tickers", [])
    has_prior_data = bool(state.get("fetched_data"))
    transcript_summary = "\n".join(
        f"[{turn.get('role')} round {turn.get('round')}] {turn.get('content', '')[:400]}"
        for turn in state.get("transcript", [])[-8:]
    )
    context = (
        f"Previous ticker(s) in context: {prior_tickers or 'none'}\n"
        f"Data already fetched for those tickers: {has_prior_data}\n"
        f"Recent debate transcript (most recent turns):\n{transcript_summary or '(none yet)'}\n"
    )

    raw = complete(
        prompt=f"{context}\nUser's latest message: {state['user_message']}",
        system=_SYSTEM_PROMPT,
        model=state.get("model"),
        provider=state.get("provider"),
        api_key=state.get("api_key"),
    )
    parsed = _extract_json(raw)

    tickers = [t.strip().upper() for t in parsed.get("tickers", []) if t.strip()] or prior_tickers
    turn_type = parsed.get("turn_type", "new_analysis")
    selected_tools = parsed.get("selected_tools", [])
    trail_event = {
        "step": "orchestrator_route",
        "ticker": None,
        "status": "done",
        "detail": f"turn_type={turn_type}, tickers={tickers}, tools={selected_tools}",
    }

    return {
        "turn_type": turn_type,
        "tickers": tickers,
        "selected_tools": selected_tools,
        "needs_fx": bool(parsed.get("needs_fx", False)),
        "out_of_scope_reason": parsed.get("out_of_scope_reason"),
        "router_notes": parsed.get("notes", ""),
        "trail": [trail_event],
    }
