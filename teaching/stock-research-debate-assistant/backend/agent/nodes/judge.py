"""Judge node: synthesizes the debate transcript into an explicit
Buy/Sell/Hold stance + reasoning + non-advice disclaimer.

This is a deliberate override of "never directive" (see
architecture_design.md's Decision Walkthrough) — the judge MUST end with
an explicit stance, not just weighed pros/cons. The disclaimer is always
appended in code (not left to the model to remember), so it can never be
silently dropped.
"""
from __future__ import annotations

import json
import re

from ..llm_client import complete
from ..state import GraphState, emit_progress

DISCLAIMER = (
    "This is not financial advice. It is an educational synthesis of the debate above, "
    "grounded only in the fetched data — verify independently and consider consulting a "
    "licensed financial advisor before making any investment decision."
)

_SYSTEM_PROMPT = """You are the judge in a stock research debate. Read the full bull, bear, \
and risk arguments below and synthesize them into a decision. You MUST end with an \
explicit stance of exactly "Buy", "Sell", or "Hold" — never a hedge like "it depends" \
with no stance. Ground your reasoning only in points actually made in the transcript \
(which are themselves grounded only in fetched data). For a two-stock comparison, \
explicitly name which stock is the stronger choice for the user's criteria and \
which is weaker. For an allocation request, explain why the deterministic \
weights fit the objective; never generate or change weights in your response.

Use plain language for a common investor. Say "usual historical ups and downs" \
instead of unexplained technical jargon. For an allocation request, do not \
recommend rebalancing ranges, new percentages, or any weights different from \
the deterministic optimizer output. The allocation output itself is the source \
of truth for all numbers.

Respond with ONLY a JSON object, no prose, no markdown fences:
{"stance": "Buy" | "Sell" | "Hold", "reasoning": "3-6 sentences synthesizing the debate and justifying the stance"}
"""


def _allocation_explanation(output: dict) -> str:
    """Explain the optimizer result without asking the model to invent numbers."""
    allocations = output.get("allocations") or []
    optimized = output.get("optimized") or {}
    equal = output.get("equal_weight") or {}
    if not allocations:
        return "The optimizer did not return an allocation."

    largest = max(allocations, key=lambda item: item.get("weight", 0))
    optimized_vol = optimized.get("annualized_volatility", 0) * 100
    equal_vol = equal.get("annualized_volatility", 0) * 100
    optimized_return = optimized.get("expected_annual_return", 0) * 100
    equal_return = equal.get("expected_annual_return", 0) * 100
    if optimized_vol <= equal_vol:
        risk_sentence = (
            f"In the historical sample, this mix moved less than splitting the money equally "
            f"({optimized_vol:.2f}% vs. {equal_vol:.2f}% annual volatility)."
        )
    else:
        risk_sentence = (
            f"In the historical sample, splitting the money equally moved less "
            f"({equal_vol:.2f}% vs. {optimized_vol:.2f}% annual volatility)."
        )
    concentration_sentence = (
        f"The largest holding is {largest['ticker']} at {largest['weight'] * 100:.1f}%, "
        "so its performance will have the biggest effect on the result."
    )
    return (
        "The computer tested the stocks' daily price movements together and chose the "
        "mix with the smallest historical portfolio swings, while keeping the weights "
        "between 0% and 100% and adding them to 100%. "
        f"{risk_sentence} The mix's historical annual return was {optimized_return:.2f}%, "
        f"compared with {equal_return:.2f}% for equal weighting. {concentration_sentence}"
    )


def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def run_judge(state: GraphState) -> dict:
    emit_progress(state, "judge_synthesis", "started", "Synthesizing the debate")
    transcript_text = "\n\n".join(
        f"[{t['role']} round {t['round']}]\n{t['content']}" for t in state.get("transcript", [])
    )
    raw = complete(
        prompt=(
            f"User's question: {state['user_message']}\n\n"
            f"Deterministic optimizer output (authoritative; never alter its numbers):\n"
            f"{state.get('allocation_output') or '(not an allocation request)'}\n\n"
            f"Full debate transcript:\n{transcript_text}"
        ),
        system=_SYSTEM_PROMPT,
        model=state.get("model"),
        provider=state.get("provider"),
        api_key=state.get("api_key"),
    )
    parsed = _extract_json(raw)
    stance = parsed.get("stance", "Hold")
    reasoning = parsed.get("reasoning", "")
    allocation_text = ""
    output = state.get("allocation_output") or {}
    if output:
        optimized = output.get("optimized", {})
        equal = output.get("equal_weight", {})
        rows = "\n".join(
            f"- {item['ticker']}: {item['weight'] * 100:.1f}% ({output['currency']} {item['amount']:,.2f}); "
            f"historical return {item['historical_return'] * 100:.2f}%"
            for item in output.get("allocations", [])
        )
        allocation_text = (
            "\n\n**Allocation from historical data**\n"
            f"{rows}\n\n"
            f"Overall historical annual return: {optimized.get('expected_annual_return', 0) * 100:.2f}%\n"
            f"Overall historical volatility (usual yearly ups and downs): {optimized.get('annualized_volatility', 0) * 100:.2f}%\n"
            f"Equal split comparison — return / volatility: {equal.get('expected_annual_return', 0) * 100:.2f}% / {equal.get('annualized_volatility', 0) * 100:.2f}%\n"
            f"How it was chosen: {_allocation_explanation(output)}\n"
            f"Data basis: {output.get('basis')} Through {output.get('history_end')}."
        )
    if output:
        final_answer = (
            "**Recommended allocation**\n\n"
            "**Investor-friendly takeaway:** The optimizer favors the mix below "
            "because it had the lowest measured historical ups and downs under "
            "the selected rules. This is a historical comparison, not a promise "
            "about the future.\n\n"
            f"**Why this split:** {_allocation_explanation(output)}"
            f"{allocation_text}\n\n_{DISCLAIMER}_"
        )
        stance = None
    else:
        final_answer = f"**Stance: {stance}**\n\n{reasoning}{allocation_text}\n\n_{DISCLAIMER}_"
    emit_progress(state, "judge_synthesis", "done", f"Final {stance} synthesis ready")

    judge_turn = {"role": "judge", "round": 1, "content": final_answer}
    return {
        "transcript": [judge_turn],
        "final_answer": final_answer,
        "stance": stance,
        "trail": [{"step": "judge_synthesis", "ticker": None, "status": "done", "detail": f"stance={stance}"}],
    }
