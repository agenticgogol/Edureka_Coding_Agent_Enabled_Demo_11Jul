"""Orchestrator/router node: classifies turn type, resolves ticker(s),
picks which fetch tools this question actually needs, and screens for the
explicit non-goal categories (out-of-scope), per architecture_design.md.

One LLM call via llm_client.complete().
"""
from __future__ import annotations

import json
import re

from .. import memory
from ..llm_client import complete
from ..state import GraphState, emit_progress
from ..tools.price_fundamentals import PEER_MAP, check_ticker_exists
from ..tools.ticker_lookup import resolve_company_name

# A bare-word ticker format check (letters, optional .NS/.BO suffix) — cheap
# pre-filter before deciding whether a resolved token needs name lookup.
_TICKER_FORMAT_RE = re.compile(r"^[A-Z]{1,10}(\.(NS|BO))?$")


def _resolve_ticker(token: str) -> tuple[str, str]:
    """Resolve one router-extracted token to a real ticker if it doesn't
    already look valid. Returns (resolved_ticker, note) — note is "" when
    no resolution was needed."""
    if not _TICKER_FORMAT_RE.match(token) or not check_ticker_exists(token).get("valid"):
        candidates = resolve_company_name(token)
        if candidates:
            top = candidates[0]
            others = ", ".join(f"{c['symbol']} on {c.get('exchange') or 'Yahoo'}" for c in candidates[1:3])
            note = f"resolved '{token}' to {top['symbol']}" + (f"; also matched {others}" if others else "")
            return top["symbol"], note
    return token, ""

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
leverage, or real \
trading / brokerage actions (e.g. "place this trade for me"). Comparing two SPECIFIC \
stocks the user names is NOT portfolio optimization and is NOT out of scope — only \
classify out_of_scope when the request matches one of these categories, not merely \
because it mentions money or stocks.
- "allocation_new": multiple tickers plus an investment amount for an allocation.
- "allocation_list_change": add or remove tickers from an existing allocation.
- "allocation_parameter_change": change target return, risk, or horizon.
- "allocation_compare": compare the existing allocation with equal weight.
- "allocation_drill_down": explain an existing allocation weight or risk contribution.
- "quick_summary": the user explicitly wants a fast/short/60-second summary or thesis on a \
ticker, not a full bull/bear/risk debate — e.g. "give me the 60-second summary of AAPL", \
"quick take on MSFT". Still needs price/fundamentals data fetched, but skips news/fx and \
the full debate.
- "critique": the user wants the EXISTING transcript (from a prior new_analysis/comparison \
turn on the same ticker(s)) reformatted or challenged — no new data fetch. Also set \
"critique_mode" to exactly one of "top_reasons" | "red_team" | "stress_test" | "bias_check": \
  - "top_reasons": "give me the top 5 reasons to buy/avoid this stock".
  - "red_team": "what am I missing", "play devil's advocate", "what's the counterargument".
  - "stress_test": "stress test this thesis", "what would have to go wrong".
  - "bias_check": "am I being biased", "check my confirmation bias", "am I just seeing what I want to see".
- "price_move_explain": the user asks WHY a stock's price moved, e.g. "why did AAPL fall today", \
"what's driving MSFT's drop this week" — reuse already-fetched price history/news for the same \
ticker(s) already in context, no full re-debate.
- "scenario_simulator": the user explicitly wants bear/base/bull scenarios or "what if" price \
ranges for an already-in-context ticker, e.g. "give me bear/base/bull cases for AAPL", "what are \
the downside and upside scenarios". These are illustrative LLM-reasoned scenarios, not a computed \
model.
- "news_materiality": the user asks whether recently fetched news actually matters / changes the \
thesis, e.g. "does this news change anything", "is this material", "should this change my view".
- "reverse_dcf": the user asks what growth rate is "priced in" or implied by the current price, \
e.g. "what growth is priced into AAPL", "reverse DCF this stock", "what growth rate justifies \
this valuation". Needs price/fundamentals data fetched (market cap, free cash flow) for the \
already-in-context or newly named ticker.
- "portfolio_stress_test": the user wants to stress-test an existing allocation against a shock, \
e.g. "what if tech drops 20%", "stress test my portfolio", "what if correlations go to 1". \
Requires an existing allocation already computed this session.

For "comparison": if the user asks to compare a ticker to "its peers"/"competitors"/"similar \
companies" without naming a second ticker, extract only the one named ticker — a curated peer will \
be looked up in code, do not invent a peer ticker yourself.

Tool selection (pick zero or more from ["price_fundamentals", "news", "fx"]), only \
relevant for new_analysis / topic_switch / comparison:
- "price_fundamentals": needed for almost any real ticker question.
- "news": needed only if the question is news/sentiment/event driven, NOT for a pure \
valuation/fundamentals-only question (e.g. "is MSFT overvalued based on P/E" does not \
need news).
- "fx": needed only for a comparison whose tickers trade in different currencies \
(e.g. one US ticker vs one Indian ticker) and the user needs a common-currency view.

For "portfolio_stress_test", also extract: "shock_ticker" (a single ticker \
the shock applies to, or null for a broad/all-tickers shock), "shock_return_shift" (a decimal \
annualized return shift, e.g. -20% becomes -0.20), and "shock_correlation_to_one" (true only if \
the user asks about correlations breaking down / going to 1).

Extract ticker symbols exactly as the user would type them into yfinance (e.g. AAPL, \
MSFT, RELIANCE.NS, TCS.NS, INFY.BO). For follow_up/drill_down/refinement, resolve \
pronouns ("it", "that stock") to the ticker(s) already in context.

For allocation turns, also extract the investment amount and currency when
present, plus a target annual return as a decimal (8% becomes 0.08). Do not
invent missing values. Respond with ONLY a JSON object, no prose, no markdown fences:
{
  "turn_type": "...",
  "tickers": ["..."],
  "selected_tools": ["..."],
  "needs_fx": true/false,
  "out_of_scope_reason": "..." or null,
  "notes": "one short sentence explaining the classification",
  "allocation_amount": number or null,
  "allocation_currency": "USD" or "INR" or null,
  "target_return": number or null,
  "critique_mode": "top_reasons" or "red_team" or "stress_test" or "bias_check" or null,
  "shock_ticker": "..." or null,
  "shock_return_shift": number or null,
  "shock_correlation_to_one": true/false
}
"""


class RouterJSONError(RuntimeError):
    """Raised when the router LLM's output isn't parseable JSON, even
    after one re-prompt asking it to fix the formatting."""


def _clean_json_text(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def _extract_json(raw: str) -> dict:
    """Parse the router's JSON output, no silent fallback.

    A single malformed response isn't necessarily worth failing the whole
    turn over, so the caller (`route`) re-prompts once with the original
    raw text asking the model to fix it; this function itself just parses
    and raises `RouterJSONError` (never returns a placeholder) on failure.
    """
    try:
        return json.loads(_clean_json_text(raw))
    except json.JSONDecodeError as exc:
        raise RouterJSONError(f"Router output was not valid JSON: {exc}") from exc


def route(state: GraphState) -> dict:
    emit_progress(state, "orchestrator_route", "started", "Classifying request and selecting tools")
    prior_tickers = state.get("tickers", [])
    has_prior_data = bool(state.get("fetched_data"))
    transcript_summary = "\n".join(
        f"[{turn.get('role')} round {turn.get('round')}] {turn.get('content', '')[:400]}"
        for turn in state.get("transcript", [])[-40:]
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
        node="orchestrator_route",
    )
    try:
        parsed = _extract_json(raw)
    except RouterJSONError:
        emit_progress(state, "orchestrator_route", "retrying", "Router output wasn't valid JSON, re-prompting once")
        retry_raw = complete(
            prompt=(
                "Your previous response was not valid JSON and could not be parsed:\n"
                f"{raw}\n\n"
                "Reply again with ONLY the corrected JSON object described in your "
                "instructions, no prose, no markdown fences."
            ),
            system=_SYSTEM_PROMPT,
            model=state.get("model"),
            provider=state.get("provider"),
            api_key=state.get("api_key"),
            node="orchestrator_route_retry",
        )
        try:
            parsed = _extract_json(retry_raw)
        except RouterJSONError as exc:
            emit_progress(state, "orchestrator_route", "error", str(exc))
            raise RouterJSONError(
                f"Router returned unparseable JSON twice in a row. Last raw output: {retry_raw!r}"
            ) from exc

    tickers = [t.strip().upper() for t in parsed.get("tickers", []) if t.strip()] or prior_tickers
    turn_type = parsed.get("turn_type", "new_analysis")
    resolution_note = ""
    # Mandatory A: only resolve for turn types that actually fetch fresh
    # data for a new/changed ticker — follow_up/drill_down/refinement etc.
    # resolve pronouns to an already-in-context ticker, not a new name.
    if turn_type in {"new_analysis", "topic_switch", "comparison"} and tickers:
        resolved = []
        notes = []
        for token in tickers:
            symbol, note = _resolve_ticker(token)
            resolved.append(symbol)
            if note:
                notes.append(note)
        tickers = resolved
        if notes:
            resolution_note = " " + "; ".join(notes) + "."
    peer_note = ""
    # Peer comparison (Phase 2 item 8): curated static map, not live
    # discovery. Only fires when the user asked to compare to "its peers"
    # without naming a second ticker (i.e. the router resolved just one).
    if turn_type == "comparison" and len(tickers) == 1:
        peers = PEER_MAP.get(tickers[0])
        if peers:
            tickers = [tickers[0], peers[0]]
            peer_note = (
                f" Peer '{peers[0]}' added from a curated static peer list, not live discovery."
            )
    if state.get("risk_profile_changed") and state.get("allocation_output"):
        turn_type = "allocation_parameter_change"
    selected_tools = parsed.get("selected_tools", [])
    allocation_requested = turn_type.startswith("allocation")
    allocation_amount = parsed.get("allocation_amount")
    if isinstance(allocation_amount, str):
        allocation_amount = float(re.sub(r"[^0-9.]", "", allocation_amount) or 0)
    if allocation_amount is None:
        allocation_amount = state.get("allocation_amount")
    allocation_currency = parsed.get("allocation_currency") or state.get("allocation_currency")
    target_return = parsed.get("target_return")
    if isinstance(target_return, (int, float)) and target_return > 1:
        target_return /= 100
    if target_return is None:
        target_return = state.get("allocation_target_return")
    trail_event = {
        "step": "orchestrator_route",
        "ticker": None,
        "status": "done",
        "detail": f"turn_type={turn_type}, tickers={tickers}, tools={selected_tools}.{peer_note}{resolution_note}",
    }
    emit_progress(state, "orchestrator_route", "done", trail_event["detail"])

    # Long-term memory reuse: pull each resolved ticker's last synthesis (if
    # any) so debate.py can hand it to the bull/bear/risk agents as
    # additional context for a fresh debate, not a shortcut around it. Read
    # here (not in __init__.py before graph.invoke) because tickers aren't
    # resolved until this point in the turn.
    prior_analysis_context = {}
    for ticker in tickers:
        past = memory.get_past_analysis(ticker)
        if past:
            prior_analysis_context[ticker] = f"({past['updated_at']}) {past['stance']}: {past['synthesis']}"

    prior_allocation_context = None
    if allocation_requested:
        prior_allocation = memory.get_latest_allocation(state["user_key"])
        if prior_allocation:
            prior_allocation_context = (
                f"({prior_allocation['updated_at']}) {prior_allocation['synthesis']}"
            )

    return {
        "turn_type": turn_type,
        "tickers": tickers,
        "prior_analysis_context": prior_analysis_context,
        "prior_allocation_context": prior_allocation_context,
        "selected_tools": selected_tools,
        "needs_fx": bool(parsed.get("needs_fx", False)),
        "out_of_scope_reason": parsed.get("out_of_scope_reason"),
        "router_notes": parsed.get("notes", "") + peer_note + resolution_note,
        "allocation_requested": allocation_requested,
        "allocation_amount": allocation_amount,
        "allocation_currency": allocation_currency,
        "allocation_target_return": target_return,
        "allocation_question": state["user_message"] if allocation_requested else None,
        "critique_mode": parsed.get("critique_mode"),
        "shock_ticker": parsed.get("shock_ticker"),
        "shock_return_shift": parsed.get("shock_return_shift") or 0.0,
        "shock_correlation_to_one": bool(parsed.get("shock_correlation_to_one", False)),
        "trail": [trail_event],
    }
