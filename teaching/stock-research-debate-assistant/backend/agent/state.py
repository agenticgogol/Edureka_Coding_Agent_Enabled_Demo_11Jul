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
from typing import Annotated, Any, Literal, TypedDict

TurnType = Literal[
    "new_analysis",
    "follow_up",
    "drill_down",
    "refinement",
    "topic_switch",
    "comparison",
    "allocation_new",
    "allocation_list_change",
    "allocation_parameter_change",
    "allocation_compare",
    "allocation_drill_down",
    "out_of_scope",
    "quick_summary",
    "critique",
    "price_move_explain",
    "scenario_simulator",
    "news_materiality",
    "reverse_dcf",
    "portfolio_stress_test",
]

ToolName = Literal["price_fundamentals", "news", "fx"]

CritiqueMode = Literal["top_reasons", "red_team", "stress_test", "bias_check"]


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


def emit_progress(state: "GraphState", step: str, status: str, detail: Any = None, ticker: str | None = None) -> None:
    callback = state.get("_progress_callback")
    if callback:
        callback({"step": step, "ticker": ticker, "status": status, "detail": detail})


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
    _progress_callback: Any

    # Orchestrator output
    turn_type: TurnType
    tickers: list[str]
    selected_tools: list[ToolName]
    needs_fx: bool
    fx_pair: tuple[str, str] | None
    out_of_scope_reason: str | None
    router_notes: str
    allocation_requested: bool
    allocation_amount: float | None
    allocation_currency: str | None
    allocation_target_return: float | None
    allocation_question: str | None
    critique_mode: "CritiqueMode | None"
    shock_ticker: str | None
    shock_return_shift: float
    shock_correlation_to_one: bool

    # Task state carried across turns
    fetched_data: Annotated[dict, _merge_dicts]
    fx_data: Annotated[dict, _merge_dicts]
    risk_tolerance: str | None
    risk_profile_changed: bool
    refinements: dict
    allocation_output: dict

    # Adaptive debate depth (Milestone 1 extension, see graph.py's
    # `_route_after_judge` and nodes/debate.py's `run_extra_round`): set to
    # True once the one allowed extra bull/bear round has run, so the
    # judge->debate_extra_round loop can fire at most once per turn (caps
    # total rounds at ROUNDS + 1 = 3).
    debate_extended: bool

    # Debate + synthesis
    transcript: Annotated[list[TranscriptTurn], operator.add]
    final_answer: str
    stance: Literal["Buy", "Sell", "Hold"] | None
    # Judge-estimated bull/bear agreement score, 0.0 (strong conflict) to
    # 1.0 (strong agreement); None for allocation turns (no bull/bear debate).
    confidence: float | None

    # Reasoning trail (ordered, discrete step events for the frontend)
    trail: Annotated[list[TrailEvent], operator.add]

    # Long-term-memory-derived context surfaced this turn (read-only note)
    memory_note: str | None

    # Prior-session memory actually fed into this turn's debate prompts
    # (not just the display-only `memory_note` above). Set once per turn by
    # orchestrator.route() once tickers are resolved, read by
    # debate._format_fetched_data / run_debate. ticker -> past synthesis text.
    prior_analysis_context: dict[str, str]
    prior_allocation_context: str | None
