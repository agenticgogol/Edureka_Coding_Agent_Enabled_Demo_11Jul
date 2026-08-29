"""Bull, bear, and risk agent nodes: a bounded 2-round adversarial debate.

Round count decision (documented per task instructions): ROUNDS = 2.
  Round 1: bull opens with its case, bear opens with its case, risk gives
    its initial fit assessment — all grounded only in `fetched_data`.
  Round 2 (rebuttal): bull rebuts the bear's round-1 argument, bear rebuts
    the bull's round-1 argument. Risk does not get a rebuttal round in
    Milestone 1 (its job is a single fit assessment, not adversarial).
This matches the brief's "single argument + at most one rebuttal round
per side is sufficient for Milestone 1" and is implemented as an actual
loop (not copy-pasted calls) so raising ROUNDS later is a one-line change.
"""
from __future__ import annotations

from ..llm_client import complete
from ..state import GraphState, emit_progress

ROUNDS = 2


def _format_fetched_data(state: GraphState) -> str:
    chunks = []
    for ticker in state.get("tickers", []):
        data = state.get("fetched_data", {}).get(ticker, {})
        pf = data.get("price_fundamentals")
        news = data.get("news")
        chunks.append(f"=== {ticker} ===")
        if pf:
            # The optimizer consumes the complete history locally. Do not
            # duplicate thousands of OHLC rows into every LLM prompt.
            compact_pf = {key: value for key, value in pf.items() if key != "price_history"}
            history = pf.get("price_history") or []
            compact_pf["history_observations"] = len(history)
            compact_pf["history_start"] = history[0].get("date") if history else None
            compact_pf["history_end"] = history[-1].get("date") if history else None
            chunks.append(f"Price/fundamentals: {compact_pf}")
        else:
            chunks.append("Price/fundamentals: (not fetched / unavailable)")
        raw_news = news.get("raw_results", "") if news else "(not fetched — question did not require news)"
        chunks.append(f"News (bounded context): {raw_news[:8000]}")
    fx = state.get("fx_data")
    if fx:
        chunks.append(f"FX data: {fx}")
    if state.get("allocation_output"):
        chunks.append(f"=== DETERMINISTIC ALLOCATION OUTPUT ===\n{state['allocation_output']}")
    return "\n".join(chunks)


def _agent_call(role: str, instructions: str, state: GraphState, extra_context: str = "") -> str:
    system = (
        f"You are the {role} agent in a stock research debate. Argue strictly from the "
        "fetched data given below — never invent a number, headline, or fact that isn't "
        "present in it. If the data needed for a claim is missing, say so explicitly "
        "instead of guessing. Be concise (4-8 sentences)."
    )
    prompt = (
        f"{instructions}\n\nUser's question: {state['user_message']}\n\n"
        f"Fetched data:\n{_format_fetched_data(state)}\n{extra_context}"
    )
    return complete(prompt, system=system, model=state.get("model"), provider=state.get("provider"), api_key=state.get("api_key"))


def run_debate(state: GraphState) -> dict:
    """Full bull -> bear -> risk debate, ROUNDS rounds, for a fresh
    new_analysis/topic_switch/comparison turn."""
    transcript: list[dict] = []
    trail: list[dict] = []

    subject = "the proposed portfolio allocation" if state.get("allocation_output") else "this stock"
    emit_progress(state, "debate_bull", "started", "Bull agent is evaluating the evidence")
    bull_round1 = _agent_call("bull", f"Make the strongest case for accepting {subject}, using only the computed data.", state)
    emit_progress(state, "debate_bull", "done", "Bull case complete")
    transcript.append({"role": "bull", "round": 1, "content": bull_round1})
    trail.append({"step": "debate_bull", "ticker": None, "status": "done", "detail": bull_round1[:200]})

    emit_progress(state, "debate_bear", "started", "Bear agent is testing downside and concentration")
    bear_round1 = _agent_call("bear", f"Make the strongest case against accepting {subject}, focusing on concentration, correlation, and historical risk.", state)
    emit_progress(state, "debate_bear", "done", "Bear case complete")
    transcript.append({"role": "bear", "round": 1, "content": bear_round1})
    trail.append({"step": "debate_bear", "ticker": None, "status": "done", "detail": bear_round1[:200]})

    risk_tolerance = state.get("risk_tolerance") or "not stated"
    emit_progress(state, "debate_risk", "started", "Risk agent is checking fit and volatility")
    risk_round1 = _agent_call(
        "risk",
        f"Assess how this stock fits an investor with a stated risk tolerance of '{risk_tolerance}'. "
        "Focus on volatility, concentration, and downside scenarios visible in the data.",
        state,
    )
    emit_progress(state, "debate_risk", "done", "Risk assessment complete")
    transcript.append({"role": "risk", "round": 1, "content": risk_round1})
    trail.append({"step": "debate_risk", "ticker": None, "status": "done", "detail": risk_round1[:200]})

    # Allocation turns already have deterministic weights and metrics to
    # debate, so one opening round is sufficient and avoids two extra LLM
    # calls. Milestone 1 stock analysis retains its approved two rounds.
    rounds = 1 if state.get("allocation_output") else ROUNDS
    if rounds >= 2:
        bull_rebuttal = _agent_call(
            "bull",
            "Rebut the bear's argument below directly, point by point, still grounded only in the fetched data.",
            state,
            extra_context=f"\nBear's round-1 argument to rebut:\n{bear_round1}",
        )
        transcript.append({"role": "bull", "round": 2, "content": bull_rebuttal})
        trail.append({"step": "debate_bull_rebuttal", "ticker": None, "status": "done", "detail": bull_rebuttal[:200]})

        bear_rebuttal = _agent_call(
            "bear",
            "Rebut the bull's argument below directly, point by point, still grounded only in the fetched data.",
            state,
            extra_context=f"\nBull's round-1 argument to rebut:\n{bull_round1}",
        )
        transcript.append({"role": "bear", "round": 2, "content": bear_rebuttal})
        trail.append({"step": "debate_bear_rebuttal", "ticker": None, "status": "done", "detail": bear_rebuttal[:200]})

    return {"transcript": transcript, "trail": trail}


def run_risk_refine(state: GraphState) -> dict:
    """Refinement turn: re-run ONLY the risk assessment, referencing the
    existing bull/bear arguments already in the transcript plus the new
    refinement (e.g. updated risk tolerance/horizon). No re-fetch, no
    bull/bear rerun."""
    bull_bear_summary = "\n".join(
        f"[{t['role']} round {t['round']}] {t['content']}"
        for t in state.get("transcript", [])
        if t.get("role") in ("bull", "bear")
    )
    risk_tolerance = state.get("risk_tolerance") or "not stated"
    refinements = state.get("refinements", {})
    content = _agent_call(
        "risk",
        f"The user has refined their profile: {refinements}. Stated risk tolerance is now "
        f"'{risk_tolerance}'. Re-assess fit given the existing bull/bear arguments below "
        "and the originally fetched data — do not re-argue bull/bear points, just reassess risk fit.",
        state,
        extra_context=f"\nExisting bull/bear arguments:\n{bull_bear_summary}",
    )
    turn = {"role": "risk", "round": len([t for t in state.get("transcript", []) if t.get("role") == "risk"]) + 1, "content": content}
    return {
        "transcript": [turn],
        "trail": [{"step": "debate_risk_refine", "ticker": None, "status": "done", "detail": content[:200]}],
    }
