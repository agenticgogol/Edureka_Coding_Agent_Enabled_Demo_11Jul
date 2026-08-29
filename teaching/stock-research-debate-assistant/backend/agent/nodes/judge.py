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
from ..state import GraphState

DISCLAIMER = (
    "This is not financial advice. It is an educational synthesis of the debate above, "
    "grounded only in the fetched data — verify independently and consider consulting a "
    "licensed financial advisor before making any investment decision."
)

_SYSTEM_PROMPT = """You are the judge in a stock research debate. Read the full bull, bear, \
and risk arguments below and synthesize them into a decision. You MUST end with an \
explicit stance of exactly "Buy", "Sell", or "Hold" — never a hedge like "it depends" \
with no stance. Ground your reasoning only in points actually made in the transcript \
(which are themselves grounded only in fetched data).

Respond with ONLY a JSON object, no prose, no markdown fences:
{"stance": "Buy" | "Sell" | "Hold", "reasoning": "3-6 sentences synthesizing the debate and justifying the stance"}
"""


def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def run_judge(state: GraphState) -> dict:
    transcript_text = "\n\n".join(
        f"[{t['role']} round {t['round']}]\n{t['content']}" for t in state.get("transcript", [])
    )
    raw = complete(
        prompt=f"User's question: {state['user_message']}\n\nFull debate transcript:\n{transcript_text}",
        system=_SYSTEM_PROMPT,
        model=state.get("model"),
        provider=state.get("provider"),
        api_key=state.get("api_key"),
    )
    parsed = _extract_json(raw)
    stance = parsed.get("stance", "Hold")
    reasoning = parsed.get("reasoning", "")
    final_answer = f"**Stance: {stance}**\n\n{reasoning}\n\n_{DISCLAIMER}_"

    judge_turn = {"role": "judge", "round": 1, "content": final_answer}
    return {
        "transcript": [judge_turn],
        "final_answer": final_answer,
        "stance": stance,
        "trail": [{"step": "judge_synthesis", "ticker": None, "status": "done", "detail": f"stance={stance}"}],
    }
