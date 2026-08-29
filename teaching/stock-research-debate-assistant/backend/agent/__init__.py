"""Public entrypoint for the stock-research-debate-assistant agent.

The backend (FastAPI) should import ONLY `run_turn` from this package —
no internal node/state shape is meant to leak across this boundary. Keep
`session_state` as an opaque dict: read/write it back verbatim between
calls, keyed by whatever session identifier the backend uses.
"""
from __future__ import annotations

import re

from . import memory
from .graph import get_graph
from .state import GraphState

_RISK_TOLERANCE_PATTERNS = {
    "conservative": r"\bconservative\b|\blow[- ]risk\b|\brisk[- ]averse\b",
    "moderate": r"\bmoderate[- ]risk\b|\bmoderate\b",
    "aggressive": r"\baggressive\b|\bhigh[- ]risk\b|\brisk[- ]tolerant\b",
}


def _extract_risk_tolerance_mention(user_message: str) -> str | None:
    lowered = user_message.lower()
    for label, pattern in _RISK_TOLERANCE_PATTERNS.items():
        if re.search(pattern, lowered):
            return label
    return None


_PERSISTABLE_KEYS = (
    "tickers",
    "fetched_data",
    "fx_data",
    "risk_tolerance",
    "refinements",
    "transcript",
    "trail",
)


def run_turn(
    session_state: dict | None,
    user_message: str,
    *,
    user_key: str,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict:
    """Runs one chat turn through the graph and returns the updated,
    fully self-contained session state plus this turn's outputs.

    Args:
        session_state: whatever this function returned as `session_state`
            on the previous call for this chat session, or None to start
            a brand-new session.
        user_message: the user's latest chat message.
        user_key: stable identity used for long-term memory lookups
            (risk tolerance persists across sessions keyed on this).
        provider/model/api_key: optional per-session overrides from the
            Streamlit sidebar; fall back to `.env` defaults when omitted.

    Returns:
        {
            "session_state": dict,       # pass back in on the next call
            "final_answer": str,         # this turn's answer text
            "stance": "Buy"|"Sell"|"Hold"|None,
            "new_trail_events": [ {step, ticker, status, detail}, ... ],
            "memory_note": str | None,   # unprompted long-term-memory context
        }
    """
    previous = session_state or {}
    previous_trail = previous.get("trail", [])

    initial_state: GraphState = {
        "user_message": user_message,
        "user_key": user_key,
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "tickers": previous.get("tickers", []),
        "fetched_data": previous.get("fetched_data", {}),
        "fx_data": previous.get("fx_data", {}),
        "risk_tolerance": previous.get("risk_tolerance") or memory.get_risk_tolerance(user_key),
        "refinements": previous.get("refinements", {}),
        "transcript": previous.get("transcript", []),
        "trail": previous_trail,
    }

    stated_tolerance = _extract_risk_tolerance_mention(user_message)
    memory_notes: list[str] = []
    if stated_tolerance:
        initial_state["risk_tolerance"] = stated_tolerance
        initial_state["refinements"] = {**initial_state["refinements"], "risk_tolerance": stated_tolerance}
        memory.save_risk_tolerance(user_key, stated_tolerance)
    elif session_state is None and initial_state["risk_tolerance"]:
        memory_notes.append(f"I remember you previously described yourself as a {initial_state['risk_tolerance']}-risk investor.")

    graph = get_graph()
    result: GraphState = graph.invoke(initial_state)

    for ticker in result.get("tickers", []):
        past = memory.get_past_analysis(ticker)
        if past and session_state is None:
            memory_notes.append(
                f"Last time you asked about {ticker}, the synthesis was {past['stance']}: {past['synthesis'][:200]}"
            )

    if result.get("stance") and result.get("tickers"):
        for ticker in result["tickers"]:
            memory.save_analysis(ticker, result.get("final_answer", ""), result.get("stance"))

    updated_session_state = {key: result.get(key, initial_state.get(key)) for key in _PERSISTABLE_KEYS}
    new_trail_events = result.get("trail", [])[len(previous_trail):]

    return {
        "session_state": updated_session_state,
        "final_answer": result.get("final_answer", ""),
        "stance": result.get("stance"),
        "new_trail_events": new_trail_events,
        "memory_note": " ".join(memory_notes) if memory_notes else None,
    }


__all__ = ["run_turn"]
