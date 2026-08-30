"""Light-answer nodes for turn types that must NOT re-run the full
fan-out or debate: drill_down, follow_up, and out_of_scope decline.
"""
from __future__ import annotations

from ..llm_client import complete
from ..state import GraphState
from ..tools.valuation import ReverseDCFError, implied_growth_rate


# Streamlit renders markdown headers (#, ##, ###) as very large bold text —
# a model that free-styles a "# Title" heading mid-answer produces a jarring
# giant-block-letters look in the UI. All light-answer prompts below append
# this so output stays readable prose/bullets with **bold** for emphasis
# only, matching the existing debate/judge answer style.
_NO_HEADERS = (
    " Format as plain prose and bullet points; use **bold** for emphasis only. "
    "Do NOT use markdown headers (#, ##, ###) anywhere in your answer."
)


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
            system="Answer the user's question about why an agent said what it said, quoting/paraphrasing only the transcript given. Be concise." + _NO_HEADERS,
            model=state.get("model"),
            provider=state.get("provider"),
            api_key=state.get("api_key"),
            node="drill_down_answer",
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
    summaries = []
    for ticker in state.get("tickers", []):
        data = state.get("fetched_data", {}).get(ticker, {})
        pf = data.get("price_fundamentals") or {}
        summaries.append(f"{ticker}: { {key: value for key, value in pf.items() if key != 'price_history'} }")
    fetched_summary = "\n".join(summaries)
    answer = complete(
        prompt=(
            f"User's follow-up question: {state['user_message']}\n\n"
            f"Already-fetched data (do not re-fetch, answer only from this):\n{fetched_summary}\n\n"
            f"Existing debate transcript:\n{_transcript_text(state)}"
        ),
        system="Answer the user's follow-up question using only the already-fetched data and transcript given. Do not invent new facts." + _NO_HEADERS,
        model=state.get("model"),
        provider=state.get("provider"),
        api_key=state.get("api_key"),
        node="follow_up_answer",
    )
    turn = {"role": "follow_up", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "follow_up_answer", "ticker": None, "status": "done", "detail": "answered from reused state, zero new tool calls"}],
    }


def answer_quick_summary(state: GraphState) -> dict:
    """One-call, 60-second bullet-style thesis over the fetched price/
    fundamentals dict only — no debate transcript, no news/fx (see
    `_route_after_orchestrator`'s quick_summary branch, which skips those
    fetches for speed/cost)."""
    summaries = []
    for ticker in state.get("tickers", []):
        data = state.get("fetched_data", {}).get(ticker, {})
        pf = data.get("price_fundamentals") or {}
        summaries.append(f"{ticker}: { {key: value for key, value in pf.items() if key != 'price_history'} }")
    fetched_summary = "\n".join(summaries)
    answer = complete(
        prompt=(
            f"User's request: {state['user_message']}\n\n"
            f"Fetched price/fundamentals data:\n{fetched_summary}"
        ),
        system=(
            "Give a fast, short 60-second-read stock summary in bullet points from the data "
            "given only: current price/valuation snapshot, one-line growth/profitability take, "
            "one-line risk flag, and a tentative Buy/Sell/Hold lean. No debate, no long prose."
        ) + _NO_HEADERS,
        model=state.get("model"),
        provider=state.get("provider"),
        api_key=state.get("api_key"),
        node="quick_summary_answer",
    )
    turn = {"role": "follow_up", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "quick_summary_answer", "ticker": None, "status": "done", "detail": "60-second summary, price/fundamentals only, no debate"}],
    }


_CRITIQUE_PROMPTS = {
    "top_reasons": "List the top 5 reasons to buy this stock and the top reasons to avoid it, drawn only from the transcript given. Bullet points, concise." + _NO_HEADERS,
    "red_team": "Play devil's advocate: what is the user likely missing or underweighting, based only on the transcript given? Be direct and specific." + _NO_HEADERS,
    "stress_test": "Stress-test the existing thesis: what would have to go wrong for this call to be badly wrong, using only the transcript given?" + _NO_HEADERS,
    "bias_check": "Check for confirmation bias: point out where the existing transcript may be one-sided or where the user might be selectively reading it, using only the transcript given." + _NO_HEADERS,
}


def answer_critique(state: GraphState) -> dict:
    """Reformats/critiques the EXISTING transcript — no new data fetch,
    same shape as `answer_drill_down`. `critique_mode` picks which of the
    four short prompt variants to use (A4-A7 collapsed into one node)."""
    transcript = _transcript_text(state)
    mode = state.get("critique_mode") or "top_reasons"
    if not transcript:
        answer = "I don't have a prior analysis in this session to critique yet — ask me to analyze a stock first."
    else:
        answer = complete(
            prompt=(
                f"User's request: {state['user_message']}\n\n"
                f"Existing debate transcript (answer ONLY from this, do not invent new facts):\n{transcript}"
            ),
            system=_CRITIQUE_PROMPTS.get(mode, _CRITIQUE_PROMPTS["top_reasons"]),
            model=state.get("model"),
            provider=state.get("provider"),
            api_key=state.get("api_key"),
            node="critique_answer",
        )
    turn = {"role": "drill_down", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "critique_answer", "ticker": None, "status": "done", "detail": f"critique_mode={mode}, answered from existing transcript, zero new tool calls"}],
    }


def _concentration_flags(output: dict) -> str:
    """Deterministic (no LLM) concentration/hidden-risk flags from the
    optimizer's already-computed `risk_contributions` and `sector_weights`
    (Phase 2 item 5) — >40% single-name or single-sector risk contribution.
    No new math beyond what `optimize_portfolio` already returns."""
    flags = []
    optimized = output.get("optimized") or {}
    risk_contributions = optimized.get("risk_contributions") or []
    total_risk = sum(risk_contributions) or 1.0
    for row, risk in zip(output.get("allocations", []), risk_contributions):
        share = risk / total_risk if total_risk else 0.0
        if share > 0.40:
            flags.append(f"{row['ticker']} alone accounts for {share * 100:.1f}% of total portfolio risk (>40%).")
    sector_weights = output.get("sector_weights") or {}
    for sector, weight in sector_weights.items():
        if weight > 0.40:
            flags.append(f"Sector '{sector}' accounts for {weight * 100:.1f}% of the allocation (>40%).")
    if not flags:
        return "No single holding or sector exceeds the 40% concentration flag threshold."
    return " ".join(flags)


def answer_allocation(state: GraphState) -> dict:
    """Answer allocation comparisons/drill-downs from stored optimizer output.

    Always includes deterministic concentration/hidden-risk flags (Phase 2
    item 5) in the prompt context so a concentration/hidden-risk question
    gets a grounded answer without a separate turn_type/LLM call — the
    flags themselves are computed in code, never invented by the model.
    """
    output = state.get("allocation_output") or {}
    if not output:
        answer = "There is no computed allocation in this session yet. Ask for an allocation first."
    else:
        answer = complete(
            prompt=(
                f"User's allocation question: {state['user_message']}\n\n"
                f"Computed optimizer output (the numbers are authoritative):\n{output}\n\n"
                f"Deterministic concentration/hidden-risk flags (code-computed, authoritative):\n"
                f"{_concentration_flags(output)}"
            ),
            system=(
                "Explain the allocation using only the computed optimizer output. "
                "Do not recompute or invent weights, returns, or risk metrics. "
                "If the user asks about concentration or hidden risk, answer using the "
                "given concentration/hidden-risk flags verbatim in substance — do not compute "
                "your own percentages. State clearly that the metrics are historical, not a forecast."
            ) + _NO_HEADERS,
            model=state.get("model"), provider=state.get("provider"), api_key=state.get("api_key"),
            node="allocation_answer",
        )
    return {
        "final_answer": answer,
        "trail": [{"step": "allocation_answer", "ticker": None, "status": "done", "detail": "answered from stored optimizer output; no recomputation"}],
    }


def _fetched_summary(state: GraphState, include_history_tail: bool = False) -> str:
    """Same compact-data pattern as `answer_follow_up`/`answer_quick_summary`,
    reused for the new price-move/scenario/materiality answers so they don't
    dump the full OHLC history into every prompt."""
    summaries = []
    for ticker in state.get("tickers", []):
        data = state.get("fetched_data", {}).get(ticker, {})
        pf = data.get("price_fundamentals") or {}
        compact_pf = {key: value for key, value in pf.items() if key != "price_history"}
        history = pf.get("price_history") or []
        if include_history_tail and history:
            compact_pf["recent_price_history"] = history[-30:]
        news = data.get("news") or {}
        summaries.append(
            f"{ticker}: {compact_pf}\nNews (if fetched): {news.get('raw_results', '(not fetched)')[:4000]}"
        )
    return "\n\n".join(summaries)


def answer_price_move(state: GraphState) -> dict:
    """NL Q&A "why did the stock fall/rise" — reasons over already-fetched
    price_history + news, no forced re-fetch (same shape as
    `answer_follow_up`/`answer_drill_down`)."""
    fetched_summary = _fetched_summary(state, include_history_tail=True)
    if not fetched_summary.strip():
        answer = "I don't have price data fetched for this ticker yet in this session — ask me to analyze it first."
    else:
        answer = complete(
            prompt=(
                f"User's question about a price move: {state['user_message']}\n\n"
                f"Already-fetched data (do not re-fetch, answer only from this — recent price history "
                f"and news if it was fetched):\n{fetched_summary}"
            ),
            system=(
                "Explain the likely drivers of the recent price move using only the recent price "
                "history and news given. If news wasn't fetched, say the move can only be described "
                "from price action, not explained by a specific news event. Do not invent headlines "
                "or catalysts not present in the data. Be concise."
            ) + _NO_HEADERS,
            model=state.get("model"), provider=state.get("provider"), api_key=state.get("api_key"),
            node="price_move_explain_answer",
        )
    turn = {"role": "follow_up", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "price_move_explain_answer", "ticker": None, "status": "done", "detail": "answered from reused price history/news, zero new tool calls"}],
    }


def answer_scenarios(state: GraphState) -> dict:
    """Bear/Base/Bull scenario simulator — one LLM call producing 3 named,
    illustrative scenarios. NOT a computed financial model: the prompt and
    output both must say so explicitly."""
    fetched_summary = _fetched_summary(state)
    answer = complete(
        prompt=(
            f"User's request: {state['user_message']}\n\n"
            f"Fetched price/fundamentals/news data:\n{fetched_summary}"
        ),
        system=(
            "Produce three named scenarios — Bear, Base, and Bull — each with 2-3 qualitative "
            "assumptions and a rough illustrative price range, reasoning only from the data given. "
            "These are ILLUSTRATIVE scenarios you are inventing from qualitative reasoning, NOT a "
            "computed financial model or forecast — say this explicitly at the top of your answer "
            "and do not present the price ranges as precise or data-derived targets."
        ) + _NO_HEADERS,
        model=state.get("model"), provider=state.get("provider"), api_key=state.get("api_key"),
        node="scenario_simulator_answer",
    )
    turn = {"role": "follow_up", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "scenario_simulator_answer", "ticker": None, "status": "done", "detail": "illustrative bear/base/bull scenarios, not a computed model"}],
    }


def answer_reverse_dcf(state: GraphState) -> dict:
    """Reverse single-stage DCF: what growth rate does the current price
    imply, given market cap and free cash flow. Follows the same
    fetch-then-one-LLM-call shape as `answer_quick_summary`/
    `answer_scenarios`; the growth-rate math itself is deterministic
    (see tools/valuation.py), the LLM only narrates the result."""
    ticker = (state.get("tickers") or [None])[0]
    pf = (state.get("fetched_data", {}).get(ticker, {}) or {}).get("price_fundamentals") or {} if ticker else {}
    market_cap = pf.get("market_cap")
    free_cashflow = pf.get("free_cashflow")
    try:
        result = implied_growth_rate(market_cap, free_cashflow)
    except ReverseDCFError as exc:
        answer = f"I couldn't compute a reverse DCF for {ticker}: {exc}"
        return {
            "final_answer": answer,
            "trail": [{"step": "reverse_dcf_answer", "ticker": ticker, "status": "error", "detail": str(exc)}],
        }
    answer = complete(
        prompt=(
            f"User's request: {state['user_message']}\n\n"
            f"Computed reverse-DCF result for {ticker} (authoritative, do not recompute):\n{result}"
        ),
        system=(
            "Explain the implied growth rate in plain language using only the given computed "
            "result. State clearly that this is a simplified single-stage (Gordon growth) DCF, "
            "not a precision valuation, and state the discount rate assumption explicitly."
        ) + _NO_HEADERS,
        model=state.get("model"), provider=state.get("provider"), api_key=state.get("api_key"),
        node="reverse_dcf_answer",
    )
    turn = {"role": "follow_up", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "reverse_dcf_answer", "ticker": ticker, "status": "done", "detail": result}],
    }


def answer_news_materiality(state: GraphState) -> dict:
    """News materiality scoring — classifies whether fetched news changes
    the existing thesis/transcript. Same shape as `answer_critique`'s
    red_team mode; reuses `_transcript_text`."""
    transcript = _transcript_text(state)
    fetched_summary = _fetched_summary(state)
    answer = complete(
        prompt=(
            f"User's request: {state['user_message']}\n\n"
            f"Fetched news/data:\n{fetched_summary}\n\n"
            f"Existing debate transcript (if any):\n{transcript or '(none yet)'}"
        ),
        system=(
            "Assess whether the fetched news is material — i.e. whether it changes the existing "
            "thesis/transcript given, or is already priced in / immaterial noise. Give a clear "
            "materiality verdict (material / not material / unclear) and a short reason, grounded "
            "only in the data and transcript given."
        ) + _NO_HEADERS,
        model=state.get("model"), provider=state.get("provider"), api_key=state.get("api_key"),
        node="news_materiality_answer",
    )
    turn = {"role": "drill_down", "round": 1, "content": answer}
    return {
        "transcript": [turn],
        "final_answer": answer,
        "trail": [{"step": "news_materiality_answer", "ticker": None, "status": "done", "detail": "materiality verdict from fetched news + existing transcript"}],
    }


_DECLINE_REASONS = {
    "mutual_funds": "This assistant analyzes individual stocks, not mutual funds.",
    "market_timing": "This assistant does not predict short-term price movements or market timing.",
    "options_derivatives": "This assistant does not cover options, derivatives, or leveraged instruments.",
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
