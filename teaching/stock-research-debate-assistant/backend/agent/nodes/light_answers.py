"""Light-answer nodes for turn types that must NOT re-run the full
fan-out or debate: drill_down, follow_up, and out_of_scope decline.
"""
from __future__ import annotations

from ..llm_client import complete
from ..state import GraphState


def _transcript_text(state: GraphState) -> str:
    return "\n\n".join(
        f"[{t['role']} round {t['round']}]\n{t['content']}" for t in state.get("transcript", [])
    )


def answer_drill_down(state: GraphState) -> dict:
    """Answers straight from the existing transcript. Per the brief, this
    needs "zero new LLM/tool calls beyond a lightweight 'answer from
    transcript' call if needed" — we make exactly one such call, no tool
    calls at all."""
    transcript = _transcript_text(state)
    if not transcript:
        answer = "I don't have a prior analysis in this session to drill into yet — ask me to analyze a stock first."
    else:
        answer = complete(
            prompt=(
                f"User's drill-down question: {state['user_message']}\n\n"
                f"Existing debate transcript (answer ONLY from this, do not invent new facts):\n{transcript}"
            ),
            system="Answer the user's question about why an agent said what it said, quoting/paraphrasing only the transcript given. Be concise.",
            model=state.get("model"),
            provider=state.get("provider"),
            api_key=state.get("api_key"),
        )
    turn = {"role": "drill_down", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "drill_down_answer", "ticker": None, "status": "done", "detail": "answered from existing transcript, zero new tool calls"}],
    }


def answer_follow_up(state: GraphState) -> dict:
    """Answers from already-fetched data + transcript, without re-running
    the fan-out or the full debate (e.g. "what about its revenue growth"
    on an already-analyzed ticker)."""
    fetched_summary = "\n".join(
        f"{ticker}: {state.get('fetched_data', {}).get(ticker)}" for ticker in state.get("tickers", [])
    )
    answer = complete(
        prompt=(
            f"User's follow-up question: {state['user_message']}\n\n"
            f"Already-fetched data (do not re-fetch, answer only from this):\n{fetched_summary}\n\n"
            f"Existing debate transcript:\n{_transcript_text(state)}"
        ),
        system="Answer the user's follow-up question using only the already-fetched data and transcript given. Do not invent new facts.",
        model=state.get("model"),
        provider=state.get("provider"),
        api_key=state.get("api_key"),
    )
    turn = {"role": "follow_up", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "follow_up_answer", "ticker": None, "status": "done", "detail": "answered from reused state, zero new tool calls"}],
    }


_DECLINE_REASONS = {
    "mutual_funds": "This assistant analyzes individual stocks, not mutual funds.",
    "market_timing": "This assistant does not predict short-term price movements or market timing.",
    "options_derivatives": "This assistant does not cover options, derivatives, or leveraged instruments.",
    "portfolio_optimization": "This assistant does not do portfolio allocation or optimization across multiple tickers.",
    "trading_execution": "This assistant cannot place trades or perform brokerage actions.",
}


def invalid_ticker(state: GraphState) -> dict:
    answer = (
        "I couldn't resolve a valid stock ticker from your message. Try a specific ticker "
        "symbol, e.g. AAPL, MSFT, RELIANCE.NS, or TCS.BO."
    )
    return {
        "final_answer": answer,
        "trail": [{"step": "invalid_ticker", "ticker": None, "status": "error", "detail": "no ticker resolved by orchestrator"}],
    }


def decline(state: GraphState) -> dict:
    reason_key = state.get("out_of_scope_reason") or "out_of_scope"
    reason_text = _DECLINE_REASONS.get(reason_key, "This request falls outside what this assistant is scoped to do.")
    answer = (
        f"{reason_text} I can analyze individual stocks (bull/bear/risk debate + a Buy/Sell/Hold "
        "synthesis) — try asking about a specific ticker instead."
    )
    return {
        "final_answer": answer,
        "trail": [{"step": "decline", "ticker": None, "status": "done", "detail": reason_key}],
    }
