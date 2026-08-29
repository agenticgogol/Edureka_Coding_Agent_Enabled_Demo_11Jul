"""Graph state shape for the stock-research-debate-assistant.

State is task-state-shaped (per architecture_design.md's memory design),
not a flat message list: current ticker(s), already-fetched data per
ticker, the full debate transcript, and mid-conversation refinements are
all first-class fields so follow-up/drill-down/refinement turns can
resolve without re-fetching or re-debating.

Reducers:
- `fetched_data` and `fx_data` merge dict-by-dict (new tickers/pairs add,
  existing ones update) so parallel fan-out fetches combine safely and
  later turns can reuse earlier fetches untouched.
- `transcript` and `trail` append-only accumulate across the whole
  session (each `run_turn` call passes in the previous turn's full list
  as the initial value).
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

TurnType = Literal[
    "new_analysis",
    "follow_up",
    "drill_down",
    "refinement",
    "topic_switch",
    "comparison",
    "out_of_scope",
]

ToolName = Literal["price_fundamentals", "news", "fx"]


def _merge_dicts(a: dict, b: dict) -> dict:
    """One-level-deep merge: top-level keys (tickers / currency pairs) merge
    their own sub-dicts rather than overwriting wholesale, so a parallel
    fan-out write of {"AAPL": {"price_fundamentals": ...}} and a sibling
    write of {"AAPL": {"news": ...}} both survive instead of one clobbering
    the other."""
    merged = dict(a or {})
    for key, value in (b or {}).items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = {**existing, **value}
        else:
            merged[key] = value
    return merged


class TrailEvent(TypedDict, total=False):
    step: str
    ticker: str | None
    status: Literal["started", "done", "skipped", "error"]
    detail: str


class TranscriptTurn(TypedDict, total=False):
    role: Literal["bull", "bear", "risk", "judge", "follow_up", "drill_down"]
    round: int
    content: str


class GraphState(TypedDict, total=False):
    # Per-turn input
    user_message: str
    user_key: str
    provider: str | None
    api_key: str | None
    model: str | None

    # Orchestrator output
    turn_type: TurnType
    tickers: list[str]
    selected_tools: list[ToolName]
    needs_fx: bool
    fx_pair: tuple[str, str] | None
    out_of_scope_reason: str | None
    router_notes: str

    # Task state carried across turns
    fetched_data: Annotated[dict, _merge_dicts]
    fx_data: Annotated[dict, _merge_dicts]
    risk_tolerance: str | None
    refinements: dict

    # Debate + synthesis
    transcript: Annotated[list[TranscriptTurn], operator.add]
    final_answer: str
    stance: Literal["Buy", "Sell", "Hold"] | None

    # Reasoning trail (ordered, discrete step events for the frontend)
    trail: Annotated[list[TrailEvent], operator.add]

    # Long-term-memory-derived context surfaced this turn (read-only note)
    memory_note: str | None
