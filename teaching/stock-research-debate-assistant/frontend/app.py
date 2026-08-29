"""
Stock Research & Debate Assistant — Streamlit frontend.

Talks to the FastAPI backend (see ../backend, and ../design.md for the
authoritative API contract). No mock mode: every response shown here comes
from a real backend call. If the backend is unreachable or returns an
error, we surface it plainly rather than fabricating a response.

NOTE ON "LIVE" TRAIL RENDERING: the API contract's `/chat` endpoint returns
the full `trail_events` list only after the whole pipeline (fan-out ->
debate -> judge) has finished — there is no incremental/streaming trail
from the backend. To still give the reasoning trail a progressive feel (as
called for in the brief), we reveal the already-complete trail events one
at a time into a placeholder with a tiny `time.sleep` between them. This is
a purely cosmetic simulation on data we already have in hand; it does not
mean steps are actually running as they appear.
"""

import os
import time
import uuid

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

PROVIDER_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}

STANCE_COLORS = {
    "buy": ("#1b5e20", "#c8e6c9"),   # dark green text, light green bg
    "sell": ("#b71c1c", "#ffcdd2"),  # dark red text, light red bg
    "hold": ("#424242", "#e0e0e0"),  # dark gray text, light gray bg
}

NON_ADVICE_DISCLAIMER = (
    "This is not financial advice. This synthesis is generated for "
    "educational purposes from fetched market data and should not be the "
    "sole basis for any investment decision. Always do your own research "
    "and consult a licensed financial advisor."
)

st.set_page_config(page_title="Stock Research & Debate Assistant", layout="wide")


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def init_state():
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "turns" not in st.session_state:
        # each turn: {"user_message": str, "response": dict|None, "error": str|None}
        st.session_state.turns = []
    if "memory_note" not in st.session_state:
        st.session_state.memory_note = None
    if "user_key" not in st.session_state:
        st.session_state.user_key = "demo_user"


init_state()


def backend_request(method, path, **kwargs):
    """Thin wrapper around requests that raises a clear error on failure."""
    url = f"{BACKEND_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=90, **kwargs)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Could not reach backend at {url}: {exc}. Is the FastAPI "
            f"server running?"
        ) from exc
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        raise RuntimeError(f"Backend returned {resp.status_code}: {detail}")
    return resp.json()


def ensure_session():
    """Create a session_id on first load if we don't have one yet."""
    if st.session_state.session_id is None:
        try:
            data = backend_request("POST", "/session/new", json={})
            st.session_state.session_id = data["session_id"]
        except RuntimeError as exc:
            st.session_state.session_id = str(uuid.uuid4())
            st.warning(
                f"Could not create a server-side session (backend "
                f"unreachable?): {exc}. Using a local placeholder session id "
                f"for now; chat requests will still fail until the backend "
                f"is up."
            )


ensure_session()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")

    st.session_state.user_key = st.text_input(
        "Your user key (identifies you for memory)",
        value=st.session_state.user_key,
        help="Used as `user_key` in the chat request so long-term memory "
        "(risk tolerance, past ticker syntheses) can be looked up across "
        "sessions.",
    )

    provider = st.selectbox("LLM provider", options=["anthropic", "openai"], index=0)
    default_model = PROVIDER_DEFAULT_MODELS[provider]
    model = st.text_input("Model name", value=default_model)
    api_key_override = st.text_input(
        "API key override (optional)",
        type="password",
        help="Leave blank to use the backend's .env default for this provider.",
    )

    st.divider()

    risk_tolerance = st.selectbox(
        "Risk tolerance",
        options=["conservative", "moderate", "aggressive"],
        index=1,
        help="Folded into your message so the risk agent grounds its "
        "assessment in this stated tolerance.",
    )

    st.divider()

    st.subheader("What I remember about you")
    if st.session_state.memory_note:
        st.info(st.session_state.memory_note)
    else:
        st.caption("Nothing surfaced yet — ask a question to see memory in action.")

    st.divider()

    if st.button("Start fresh session", use_container_width=True):
        try:
            data = backend_request("POST", "/session/new", json={})
            st.session_state.session_id = data["session_id"]
            st.session_state.turns = []
            st.session_state.memory_note = None
            st.success(f"New session started: {st.session_state.session_id}")
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))

    st.caption(f"Session ID: `{st.session_state.session_id}`")
    st.caption(f"Backend: `{BACKEND_URL}`")


# ---------------------------------------------------------------------------
# Rendering helpers for trail events and visualizations
# ---------------------------------------------------------------------------

def render_stat_cards(detail: dict):
    """Render key numeric fields from a price/fundamentals trail event as
    st.metric stat cards, defensively — field names are not guaranteed by
    the contract beyond being "loosely typed", so we probe common keys.
    """
    if not isinstance(detail, dict):
        return
    candidate_fields = [
        ("price", "Price"),
        ("current_price", "Price"),
        ("last_price", "Price"),
        ("pe_ratio", "P/E Ratio"),
        ("pe", "P/E Ratio"),
        ("trailing_pe", "P/E Ratio"),
        ("market_cap", "Market Cap"),
        ("marketCap", "Market Cap"),
        ("revenue_growth", "Revenue Growth"),
        ("dividend_yield", "Dividend Yield"),
        ("fifty_two_week_high", "52W High"),
        ("fifty_two_week_low", "52W Low"),
    ]
    found = []
    seen_labels = set()
    for key, label in candidate_fields:
        if key in detail and label not in seen_labels and detail[key] is not None:
            found.append((label, format_metric_value(label, detail[key], detail.get("currency"))))
            seen_labels.add(label)
    if not found:
        return
    cols = st.columns(min(len(found), 4))
    for i, (label, value) in enumerate(found):
        with cols[i % len(cols)]:
            st.metric(label, str(value))


def compact_number(value, decimals: int = 2) -> str:
    """Format large financial values so cards remain readable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    for threshold, suffix in ((1_000_000_000_000, "Tn"),
                              (1_000_000_000, "Bn"),
                              (1_000_000, "Mn"),
                              (1_000, "K")):
        if abs(number) >= threshold:
            return f"{number / threshold:,.{decimals}f}{suffix}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def format_metric_value(label: str, value, currency: str | None = None) -> str:
    if label == "Market Cap" or label in {"Price", "52W High", "52W Low"}:
        prefix = f"{currency} " if currency else ""
        return prefix + compact_number(value)
    if label in {"Revenue Growth", "Dividend Yield"}:
        try:
            return f"{float(value) * 100:.2f}%"
        except (TypeError, ValueError):
            return str(value)
    return compact_number(value)


def render_price_chart(detail: dict):
    """Render a line chart from OHLC/price-history data if present.

    ASSUMPTION (flag for backend-builder/integrator): we look for a
    `history` or `price_history` list of records with a date-like key and
    a close-like key (e.g. `close`, `Close`, `adj_close`). The exact key
    names are not pinned in the contract given to this builder, so this is
    rendered defensively and silently skipped if the shape doesn't match.
    """
    if not isinstance(detail, dict):
        return
    history = detail.get("history") or detail.get("price_history")
    if not history or not isinstance(history, list):
        return
    try:
        import pandas as pd

        df = pd.DataFrame(history)
        date_col = next(
            (c for c in df.columns if c.lower() in ("date", "datetime", "timestamp")),
            None,
        )
        close_col = next(
            (c for c in df.columns if c.lower() in ("close", "adj_close", "adjclose", "price")),
            None,
        )
        if date_col and close_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.set_index(date_col)
            st.line_chart(df[[close_col]])
        elif close_col:
            st.line_chart(df[[close_col]])
    except Exception as exc:  # pragma: no cover - defensive UI-only path
        st.caption(f"(Could not render price chart from this event: {exc})")


def render_fundamentals_comparison(detail: dict):
    """Render a bar chart comparing two tickers' fundamentals, if the event
    shape looks like a comparison payload.

    ASSUMPTION: we look for `detail["tickers"]` mapping ticker -> metrics
    dict, e.g. {"AAPL": {"pe_ratio": 30, ...}, "MSFT": {...}}. This shape is
    not pinned by the contract given to this builder and should be verified
    against the actual backend comparison event.
    """
    if not isinstance(detail, dict):
        return
    tickers_data = detail.get("tickers") or detail.get("comparison")
    if not isinstance(tickers_data, dict) or len(tickers_data) < 2:
        return
    try:
        import pandas as pd

        df = pd.DataFrame(tickers_data).T
        numeric_cols = [c for c in df.columns if df[c].apply(lambda v: isinstance(v, (int, float))).all()]
        if numeric_cols:
            st.bar_chart(df[numeric_cols])
    except Exception as exc:  # pragma: no cover
        st.caption(f"(Could not render comparison chart from this event: {exc})")


def render_stance_banner(step_dict: dict):
    """Render the judge's Buy/Sell/Hold stance as a colored banner, plus
    reasoning and a persistent non-advice disclaimer.
    """
    detail = step_dict.get("detail") or {}
    stance = None
    reasoning = None
    disclaimer = None
    if isinstance(detail, dict):
        stance = detail.get("stance")
        reasoning = detail.get("reasoning") or detail.get("synthesis")
        disclaimer = detail.get("disclaimer")

    if stance:
        stance_key = str(stance).lower()
        text_color, bg_color = STANCE_COLORS.get(stance_key, ("#000", "#eee"))
        st.markdown(
            f"""
            <div style="background-color:{bg_color}; color:{text_color};
                        padding: 0.75rem 1rem; border-radius: 0.5rem;
                        font-weight: 700; font-size: 1.1rem; text-align:center;
                        margin-bottom: 0.5rem;">
                Stance: {str(stance).upper()}
            </div>
            """,
            unsafe_allow_html=True,
        )
    if reasoning:
        st.markdown(f"**Reasoning:** {reasoning}")
    st.caption(f"Disclaimer: {disclaimer or NON_ADVICE_DISCLAIMER}")


def render_trail_step(step_dict: dict):
    """Render a single trail_events item defensively. `detail`'s inner
    shape is loosely typed per the contract (varies by step name), so we
    str()-fall-back anything we don't specifically recognize.
    """
    step_name = step_dict.get("step", "unknown_step")
    status = step_dict.get("status", "unknown")
    ticker = step_dict.get("ticker")
    detail = step_dict.get("detail")

    label = f"**{step_name}**"
    if ticker:
        label += f" ({ticker})"
    label += f" — {status}"
    st.markdown(label)

    if step_name in ("fetch_price_fundamentals",) and isinstance(detail, dict):
        render_stat_cards(detail)
        render_price_chart(detail)
    elif "compar" in step_name and isinstance(detail, dict):
        render_fundamentals_comparison(detail)
        render_stat_cards(detail)
    elif "judge" in step_name or "synthesis" in step_name:
        render_stance_banner(step_dict)
    elif isinstance(detail, dict):
        # generic detail dict (e.g. bull/bear/risk argument text, news
        # headlines) — render known text-ish fields, else raw fallback.
        text_field = None
        for key in ("argument", "text", "summary", "headlines", "content"):
            if key in detail:
                text_field = detail[key]
                break
        if text_field is not None:
            if isinstance(text_field, list):
                for item in text_field:
                    st.markdown(f"- {item}")
            else:
                st.write(text_field)
        else:
            st.json(detail)
    elif detail is not None:
        st.write(str(detail))


def render_trail_events(trail_events: list, simulate_reveal: bool = False):
    """Render a list of trail events into the current container.

    If `simulate_reveal` is True, reveal events one at a time with a short
    delay using st.empty() placeholders (see module docstring for why this
    is a cosmetic simulation, not real streaming).
    """
    if not trail_events:
        st.caption("No reasoning trail steps for this turn.")
        return

    if simulate_reveal:
        placeholders = [st.empty() for _ in trail_events]
        for ph, step_dict in zip(placeholders, trail_events):
            with ph.container():
                render_trail_step(step_dict)
            time.sleep(0.25)
    else:
        for step_dict in trail_events:
            render_trail_step(step_dict)
            st.markdown("---")


PROGRESS_LABELS = {
    "orchestrator_route": "Router",
    "fetch_price_fundamentals": "Price & fundamentals",
    "fetch_news": "Recent news",
    "fetch_fx": "Currency conversion",
    "fundamentals_comparison": "Comparison",
    "debate_bull": "Bull case",
    "debate_bear": "Bear case",
    "debate_risk": "Risk assessment",
    "debate_bull_rebuttal": "Bull rebuttal",
    "debate_bear_rebuttal": "Bear rebuttal",
    "debate_risk_refine": "Risk refinement",
    "judge_synthesis": "Judge synthesis",
    "drill_down_answer": "Transcript drill-down",
    "follow_up_answer": "Follow-up answer",
    "decline": "Scope check",
    "invalid_ticker": "Ticker validation",
}


def render_progress_overview(trail_events: list):
    """Show an at-a-glance status view before the detailed trail."""
    if not trail_events:
        return
    total = len(trail_events)
    completed = sum(event.get("status") in {"done", "skipped"} for event in trail_events)
    failed = sum(event.get("status") == "error" for event in trail_events)
    st.progress(completed / total, text=f"Agent progress: {completed}/{total} stages complete")
    summary_parts = []
    for event in trail_events:
        status = event.get("status", "unknown")
        icon = {"done": "✅", "skipped": "⏭️", "error": "❌", "started": "🔄"}.get(status, "•")
        label = PROGRESS_LABELS.get(event.get("step"), event.get("step", "Unknown step"))
        summary_parts.append(f"{icon} {label}")
    st.caption("  ·  ".join(summary_parts))
    if failed:
        st.warning(f"{failed} stage{'s' if failed != 1 else ''} reported an error. See details below.")


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

st.title("Stock Research & Debate Assistant")
st.caption(
    "Bull vs. bear vs. risk debate, grounded in live price/fundamentals and "
    "news, ending in an explicit judge synthesis. Educational demo only — "
    "not financial advice."
)

trail_container = st.container()
chat_container = st.container()

with trail_container:
    st.subheader("Reasoning trail (persistent — grows down the page)")
    if not st.session_state.turns:
        st.caption("Ask a question below to see the reasoning trail fill in.")
    for i, turn in enumerate(st.session_state.turns):
        with st.expander(
            f"Turn {i + 1}: \"{turn['user_message']}\"",
            expanded=True,
        ):
            if turn.get("error"):
                st.error(turn["error"])
                continue
            response = turn.get("response") or {}
            render_progress_overview(response.get("trail_events", []))
            render_trail_events(
                response.get("trail_events", []),
                simulate_reveal=turn.get("simulate_reveal", False),
            )
            st.markdown("### Final answer")
            final_answer = response.get("final_answer")
            stance = response.get("stance")
            if stance:
                text_color, bg_color = STANCE_COLORS.get(str(stance).lower(), ("#000", "#eee"))
                st.markdown(
                    f"""
                    <div style="background-color:{bg_color}; color:{text_color};
                                padding: 0.75rem 1rem; border-radius: 0.5rem;
                                font-weight: 700; font-size: 1.2rem; text-align:center;
                                margin-bottom: 0.5rem;">
                        {str(stance).upper()}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if final_answer:
                st.write(final_answer)
            st.caption(f"Disclaimer: {NON_ADVICE_DISCLAIMER}")

with chat_container:
    st.subheader("Ask a question")
    with st.form("chat_form", clear_on_submit=True):
        user_message = st.text_area(
            "Your message",
            placeholder='e.g. "Should I invest in AAPL right now?"',
            height=80,
        )
        submitted = st.form_submit_button("Send")

    if submitted and user_message.strip():
        composed_message = (
            f"[Stated risk tolerance: {risk_tolerance}] {user_message.strip()}"
        )

        payload = {
            "session_id": st.session_state.session_id,
            "message": composed_message,
            "user_key": st.session_state.user_key,
            "provider": provider or None,
            "model": model or None,
            "api_key": api_key_override or None,
        }

        turn_record = {"user_message": user_message.strip(), "response": None, "error": None}

        with st.spinner("Running fan-out + debate + judge pipeline..."):
            try:
                response = backend_request("POST", "/chat", json=payload)
                turn_record["response"] = response
                turn_record["simulate_reveal"] = True
                memory_note = response.get("memory_note")
                if memory_note:
                    st.session_state.memory_note = memory_note
            except RuntimeError as exc:
                turn_record["error"] = str(exc)

        st.session_state.turns.append(turn_record)
        st.rerun()
