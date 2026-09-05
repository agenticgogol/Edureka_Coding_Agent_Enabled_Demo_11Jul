"""
Stock Research & Debate Assistant — Streamlit frontend.

Talks to the FastAPI backend (see ../backend, and ../design.md for the
authoritative API contract). No mock mode: every response shown here comes
from a real backend call. If the backend is unreachable or returns an
error, we surface it plainly rather than fabricating a response.

AUTH: there is no more free-text `user_key` field. On first load (or when
the user clicks "New session token") we call `POST /auth/session` once to
get a server-issued `token` (mapped server-side to a random `user_key`),
store it in `st.session_state.session_token`, and send it back as the
`X-Session-Token` header on every subsequent `/chat*` and `/session/*`
request. The token is displayed (copyable) in the sidebar so the user can
save it and paste it back in later to resume as the same identity.

STREAMING: the main chat flow calls `POST /chat/stream`, a genuine
Server-Sent-Events endpoint. We stream the response with `requests`
(`stream=True`, `resp.iter_lines()`), parse `data: {...}` lines as they
arrive, and render each trail event into the UI the moment the backend
graph actually reaches that step — no polling, no simulated/drip replay.
"""

import json
import os
import threading
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
    "groq": "llama-3.3-70b-versatile",
    "kimi": "kimi-k2-0711-preview",
    "glm": "glm-4-plus",
    "deepseek": "deepseek-chat",
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
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

def escape_markdown_dollars(text: str) -> str:
    """Streamlit's markdown renders `$...$` as inline LaTeX (KaTeX) — any two
    unescaped `$` in the same LLM-generated answer (e.g. "$98.8 billion" ...
    later "$17.7 billion") get parsed as one math expression, swallowing the
    whitespace between them and rendering in an italic serif math font. LLM
    output routinely contains raw dollar amounts, so escape every `$` before
    rendering any free-form model text — this is the one shared place that
    fix belongs, not a per-prompt instruction that can't be guaranteed."""
    if not isinstance(text, str):
        return text
    return text.replace("$", "\\$")


st.set_page_config(page_title="Stock Research App - developed by Edureka Team", layout="wide")


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def init_state():
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "session_token" not in st.session_state:
        st.session_state.session_token = None
    if "user_key" not in st.session_state:
        st.session_state.user_key = None
    if "turns" not in st.session_state:
        # each turn: {"user_message": str, "response": dict|None, "error": str|None}
        st.session_state.turns = []
    if "memory_note" not in st.session_state:
        st.session_state.memory_note = None
    if "risk_tolerance" not in st.session_state:
        st.session_state.risk_tolerance = "moderate"
    if "stream_state" not in st.session_state:
        # in-flight streaming turn, updated by a background thread and
        # polled/rendered by an st.fragment (see render_active_stream below)
        st.session_state.stream_state = None


init_state()

# Streamlit does not allow changing a widget's key after that widget has been
# created during the current script run. Chat-driven profile changes are
# therefore staged and applied at the top of the next run.
_VALID_RISK_PROFILES = {"conservative", "moderate", "aggressive"}
if st.session_state.get("risk_tolerance_pending") in _VALID_RISK_PROFILES:
    st.session_state.risk_tolerance = st.session_state.pop("risk_tolerance_pending")


def auth_headers() -> dict:
    if st.session_state.session_token:
        return {"X-Session-Token": st.session_state.session_token}
    return {}


def backend_request(method, path, **kwargs):
    """Thin wrapper around requests that raises a clear error on failure.

    Automatically attaches the `X-Session-Token` header (if we have one)
    unless the caller passes `auth=False`.
    """
    use_auth = kwargs.pop("auth", True)
    url = f"{BACKEND_URL}{path}"
    headers = kwargs.pop("headers", {}) or {}
    if use_auth:
        headers = {**auth_headers(), **headers}
    try:
        resp = requests.request(method, url, timeout=kwargs.pop("timeout", 90), headers=headers, **kwargs)
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


def ensure_auth_session():
    """Mint a session token on first load if we don't have one yet."""
    if st.session_state.session_token is None:
        try:
            data = backend_request("POST", "/auth/session", json={}, auth=False)
            st.session_state.session_token = data["token"]
            st.session_state.user_key = data["user_key"]
        except RuntimeError as exc:
            st.error(
                f"Could not create a server-side auth session (backend "
                f"unreachable?): {exc}. Chat requests will fail until the "
                f"backend is up — reload this page once it is."
            )
            st.stop()


ensure_auth_session()


def ensure_conversation_session():
    """Create a session_id on first load if we don't have one yet."""
    if st.session_state.session_id is None:
        try:
            data = backend_request("POST", "/session/new", json={})
            st.session_state.session_id = data["session_id"]
        except RuntimeError as exc:
            st.warning(f"Could not create a server-side session: {exc}")


ensure_conversation_session()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")

    st.subheader("Session identity")
    st.caption(
        "Your identity is a server-issued token (no free-text user key "
        "anymore). Save this token to resume as the same user later — "
        "long-term memory (risk tolerance, past ticker syntheses) is keyed "
        "off it."
    )
    st.code(st.session_state.session_token or "", language=None)
    st.caption(f"Resolved user_key: `{st.session_state.user_key}`")

    if st.button("New session token", width="stretch"):
        try:
            data = backend_request("POST", "/auth/session", json={}, auth=False)
            st.session_state.session_token = data["token"]
            st.session_state.user_key = data["user_key"]
            st.session_state.memory_note = None
            st.success("New session token issued.")
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))

    paste_token = st.text_input("Paste a session token to resume as that user", value="")
    if st.button("Use pasted token", width="stretch") and paste_token.strip():
        st.session_state.session_token = paste_token.strip()
        st.session_state.user_key = None  # unknown until first authenticated call succeeds
        st.session_state.memory_note = None
        st.success("Session token updated.")
        st.rerun()

    provider = st.selectbox(
        "LLM provider",
        options=["anthropic", "openai", "groq", "kimi", "glm", "deepseek", "openrouter"],
        index=0,
        help="kimi/glm/deepseek/openrouter are OpenAI-API-compatible providers "
        "(paid and free-tier models, e.g. openrouter's `:free` model IDs) — "
        "they have no .env default in this app, so an API key override below "
        "is required for them.",
    )
    default_model = PROVIDER_DEFAULT_MODELS[provider]
    model = st.text_input("Model name", value=default_model)
    api_key_override = st.text_input(
        "Your API key (required)",
        type="password",
        help="This public demo does not use the server's own API key for chat — "
        "paste your own key for the selected provider. It's sent per-request, "
        "never stored server-side.",
    )
    if not api_key_override:
        st.warning(f"Paste your own '{provider}' API key above before sending a message.")

    st.divider()

    risk_tolerance = st.selectbox(
        "Risk tolerance",
        options=["conservative", "moderate", "aggressive"],
        help="Folded into your message so the risk agent grounds its "
        "assessment in this stated tolerance.",
        key="risk_tolerance",
    )

    st.divider()
    allocation_mode = st.checkbox("Allocation mode", value=False)
    allocation_tickers = ""
    allocation_amount = 0.0
    allocation_currency = "USD"
    allocation_target = 0.0
    if allocation_mode:
        allocation_tickers = st.text_input(
            "Portfolio tickers",
            placeholder="AAPL, MSFT, JNJ",
            help="Optional structured input for allocation questions. You can also provide tickers in chat.",
        )
        allocation_amount = st.number_input("Investment amount", min_value=0.0, value=100000.0, step=1000.0)
        allocation_currency = st.selectbox("Allocation currency", options=["USD", "INR"], index=0)
        allocation_target = st.number_input(
            "Target annual return (%) — optional",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.5,
        )

    st.divider()

    st.subheader("What I remember about you")
    if st.session_state.memory_note:
        st.info(escape_markdown_dollars(st.session_state.memory_note))
    else:
        st.caption("Nothing surfaced yet — ask a question to see memory in action.")

    st.divider()

    if st.button("Start fresh session", width="stretch"):
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

    st.divider()
    st.subheader("Resume a previous session")
    st.caption(
        "Pulls the exact per-turn chat history for a session id via "
        "`GET /session/{id}/turns` (requires your session token above to "
        "be a valid, authenticated token)."
    )
    resume_session_id = st.text_input("Session ID to resume", value="", key="resume_session_id_input")
    if st.button("Resume session", width="stretch") and resume_session_id.strip():
        try:
            history = backend_request("GET", f"/session/{resume_session_id.strip()}/turns", timeout=15)
            st.session_state.session_id = resume_session_id.strip()
            turns = history.get("turns", [])
            st.session_state.turns = [
                {"user_message": f"Turn {idx + 1} (resumed)", "response": turn, "error": None}
                for idx, turn in enumerate(turns)
            ]
            st.success(f"Resumed session `{resume_session_id.strip()}` with {len(turns)} turn(s).")
            st.rerun()
        except RuntimeError as exc:
            st.error(f"Could not resume session: {exc}")


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
    """Render a candlestick chart from OHLC/price-history data if present,
    falling back to a plotly line chart if only close prices are available.

    ASSUMPTION (flag for backend-builder/integrator): we look for a
    `history` or `price_history` list of records with a date-like key and
    OHLC-ish keys (e.g. `open`/`high`/`low`/`close`). The exact key names
    are not pinned in the contract given to this builder, so this is
    rendered defensively and silently skipped if the shape doesn't match.
    """
    if not isinstance(detail, dict):
        return
    history = detail.get("history") or detail.get("price_history")
    if not history or not isinstance(history, list):
        return
    try:
        import pandas as pd
        import plotly.graph_objects as go

        df = pd.DataFrame(history)
        date_col = next(
            (c for c in df.columns if c.lower() in ("date", "datetime", "timestamp")),
            None,
        )

        def _col(*names):
            return next((c for c in df.columns if c.lower() in names), None)

        open_col, high_col, low_col, close_col = (
            _col("open"),
            _col("high"),
            _col("low"),
            _col("close", "adj_close", "adjclose", "price"),
        )
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        x_values = df[date_col] if date_col else df.index

        if all([open_col, high_col, low_col, close_col]):
            fig = go.Figure(
                data=[
                    go.Candlestick(
                        x=x_values,
                        open=df[open_col],
                        high=df[high_col],
                        low=df[low_col],
                        close=df[close_col],
                    )
                ]
            )
            fig.update_layout(
                title="Price history (candlestick)",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, width="stretch")
        elif close_col:
            fig = go.Figure(data=[go.Scatter(x=x_values, y=df[close_col], mode="lines", name="Close")])
            fig.update_layout(title="Price history", margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")
    except Exception as exc:  # pragma: no cover - defensive UI-only path
        st.caption(f"(Could not render price chart from this event: {exc})")


def render_fundamentals_comparison(detail: dict):
    """Render a plotly overlay/comparison chart for two tickers' metrics or
    price history, if the event shape looks like a comparison payload.

    ASSUMPTION: we look for `detail["tickers"]` mapping ticker -> metrics
    dict, e.g. {"AAPL": {"pe_ratio": 30, ...}, "MSFT": {...}}. If each
    ticker's dict also carries a `history`/`price_history` list, we overlay
    close-price lines instead of a bar chart. This shape is not pinned by
    the contract given to this builder and should be verified against the
    actual backend comparison event.
    """
    if not isinstance(detail, dict):
        return
    tickers_data = detail.get("tickers") or detail.get("comparison")
    if not isinstance(tickers_data, dict) or len(tickers_data) < 2:
        return
    try:
        import pandas as pd
        import plotly.graph_objects as go

        has_history = any(
            isinstance(v, dict) and (v.get("history") or v.get("price_history")) for v in tickers_data.values()
        )
        if has_history:
            fig = go.Figure()
            for ticker, metrics in tickers_data.items():
                history = metrics.get("history") or metrics.get("price_history") if isinstance(metrics, dict) else None
                if not history:
                    continue
                hdf = pd.DataFrame(history)
                date_col = next((c for c in hdf.columns if c.lower() in ("date", "datetime", "timestamp")), None)
                close_col = next(
                    (c for c in hdf.columns if c.lower() in ("close", "adj_close", "adjclose", "price")), None
                )
                if not close_col:
                    continue
                x_values = pd.to_datetime(hdf[date_col], errors="coerce") if date_col else hdf.index
                fig.add_trace(go.Scatter(x=x_values, y=hdf[close_col], mode="lines", name=ticker))
            fig.update_layout(title="Price comparison", margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")
            return

        df = pd.DataFrame(tickers_data).T
        numeric_cols = [c for c in df.columns if df[c].apply(lambda v: isinstance(v, (int, float))).all()]
        if numeric_cols:
            fig = go.Figure()
            for col in numeric_cols:
                fig.add_trace(go.Bar(name=col, x=df.index, y=df[col]))
            fig.update_layout(barmode="group", title="Fundamentals comparison", margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")
    except Exception as exc:  # pragma: no cover
        st.caption(f"(Could not render comparison chart from this event: {exc})")


def render_allocation(detail: dict):
    """Render optimizer-owned weights, amounts, return, risk, and sectors."""
    if not isinstance(detail, dict):
        return
    import pandas as pd

    optimized = detail.get("optimized") or {}
    equal = detail.get("equal_weight") or {}
    cols = st.columns(4)
    cols[0].metric("Historical return", f"{optimized.get('expected_annual_return', 0) * 100:.2f}%")
    cols[1].metric("Historical volatility", f"{optimized.get('annualized_volatility', 0) * 100:.2f}%")
    cols[2].metric("Equal-weight return", f"{equal.get('expected_annual_return', 0) * 100:.2f}%")
    cols[3].metric("Equal-weight volatility", f"{equal.get('annualized_volatility', 0) * 100:.2f}%")
    optimized_vol = optimized.get("annualized_volatility", 0)
    equal_vol = equal.get("annualized_volatility", 0)
    if optimized_vol <= equal_vol:
        st.info(
            f"**Takeaway:** The optimized mix had {((equal_vol - optimized_vol) * 100):.2f} percentage points less historical volatility than equal weighting. "
            "That means smaller typical swings in this historical sample—not guaranteed lower risk going forward."
        )
    else:
        st.warning(
            "**Takeaway:** Equal weighting had lower historical volatility than the optimized mix in this sample. "
            "Review the trade-off before using the optimizer result."
        )
    allocations = detail.get("allocations") or []
    if allocations:
        table = pd.DataFrame(allocations)
        table["weight"] = table["weight"].map(lambda value: f"{value * 100:.1f}%")
        table["amount"] = table["amount"].map(lambda value: f"{detail.get('currency', '')} {value:,.2f}")
        table["historical_return"] = table["historical_return"].map(lambda value: f"{value * 100:.2f}%")
        table["risk_contribution"] = table["risk_contribution"].map(lambda value: f"{value * 100:.2f}%")
        st.dataframe(table[["ticker", "weight", "amount", "historical_return", "risk_contribution", "sector"]], hide_index=True, width="stretch")
        st.subheader("Where the money goes")
        st.caption("Takeaway: taller bars mean more of the investment is assigned to that stock.")
        st.bar_chart(pd.DataFrame({item["ticker"]: [item["weight"]] for item in allocations}, index=["optimized weight"]))
    sectors = detail.get("sector_weights") or {}
    if sectors:
        st.caption("Sector concentration")
        largest_sector, largest_weight = max(sectors.items(), key=lambda item: item[1])
        st.caption(f"Takeaway: {largest_sector} is the largest sector at {largest_weight * 100:.1f}% of the portfolio.")
        st.bar_chart(pd.DataFrame({key: [value] for key, value in sectors.items()}, index=["portfolio weight"]))


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

    icon = {"done": "✅", "skipped": "⏭️", "error": "❌", "started": "🔄"}.get(status, "•")
    label = f"{icon} **{PROGRESS_LABELS.get(step_name, step_name)}**"
    if ticker:
        label += f" ({ticker})"
    st.caption(label)

    if step_name in ("fetch_price_fundamentals",) and isinstance(detail, dict):
        render_stat_cards(detail)
        render_price_chart(detail)
    elif step_name == "portfolio_optimization" and isinstance(detail, dict):
        render_allocation(detail)
    elif step_name == "fundamentals_comparison" and isinstance(detail, dict):
        render_fundamentals_comparison(detail)
        render_stat_cards(detail)
    elif "judge" in step_name or "synthesis" in step_name:
        render_stance_banner(step_dict)
    elif step_name == "reverse_dcf_answer" and isinstance(detail, dict):
        if not {"discount_rate", "implied_growth_rate", "market_cap", "free_cashflow"} <= detail.keys():
            st.json(detail)
        else:
            cols = st.columns(4)
            cols[0].metric("Implied growth rate", format_metric_value("Revenue Growth", detail.get("implied_growth_rate")))
            cols[1].metric("Discount rate", format_metric_value("Revenue Growth", detail.get("discount_rate")))
            cols[2].metric("Market cap", format_metric_value("Market Cap", detail.get("market_cap")))
            cols[3].metric("Free cash flow", format_metric_value("Market Cap", detail.get("free_cashflow")))
            if detail.get("model"):
                st.caption(f"Model: {detail['model']}")
    elif step_name == "portfolio_stress_test" and isinstance(detail, dict):
        before = detail.get("before") or {}
        after = detail.get("after") or {}
        cols = st.columns(2)
        before_return = before.get("expected_annual_return", 0)
        after_return = after.get("expected_annual_return", 0)
        before_vol = before.get("annualized_volatility", 0)
        after_vol = after.get("annualized_volatility", 0)
        cols[0].metric("Expected annual return", f"{after_return * 100:.2f}%", delta=f"{(after_return - before_return) * 100:.2f}%")
        cols[1].metric("Annualized volatility", f"{after_vol * 100:.2f}%", delta=f"{(after_vol - before_vol) * 100:.2f}%", delta_color="inverse")
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
                    st.markdown(f"- {escape_markdown_dollars(str(item))}")
            else:
                st.write(escape_markdown_dollars(str(text_field)))
        else:
            st.json(detail)
    elif detail is not None:
        st.write(escape_markdown_dollars(str(detail)))


def render_trail_events(trail_events: list):
    """Render a list of trail events into the current container."""
    if not trail_events:
        st.caption("No reasoning trail steps for this turn.")
        return
    for step_dict in trail_events:
        render_trail_step(step_dict)
        st.markdown("---")


PROGRESS_LABELS = {
    "orchestrator_route": "Router",
    "fetch_price_fundamentals": "Price & fundamentals",
    "fetch_news": "Recent news",
    "fetch_fx": "Currency conversion",
    "portfolio_optimization": "Compute optimized weights",
    "allocation_result": "Allocation result",
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
    "debate_bull_extra": "Bull follow-up round",
    "debate_bear_extra": "Bear follow-up round",
    "quick_summary_answer": "60-second summary",
    "critique_answer": "Critique",
    "price_move_explain_answer": "Price move explained",
    "scenario_simulator_answer": "Bear/Base/Bull scenarios",
    "reverse_dcf_answer": "Implied growth (reverse DCF)",
    "news_materiality_answer": "News materiality check",
    "allocation_answer": "Allocation explanation",
    "portfolio_stress_test": "Portfolio stress test",
}


def render_progress_overview(trail_events: list):
    """Show an at-a-glance status view before the detailed trail."""
    if not trail_events:
        return
    latest_by_step = {}
    order = []
    for event in trail_events:
        key = (event.get("step"), event.get("ticker"))
        if key not in latest_by_step:
            order.append(key)
        latest_by_step[key] = event
    events = [latest_by_step[key] for key in order]
    total = len(events)
    completed = sum(event.get("status") in {"done", "skipped"} for event in events)
    failed = sum(event.get("status") == "error" for event in events)
    in_progress = next((e for e in events if e.get("status") == "started"), None)
    if in_progress:
        narration = f"Currently: {PROGRESS_LABELS.get(in_progress.get('step'), in_progress.get('step', 'working'))}..."
    elif completed == total:
        narration = "Done — see the reasoning trail below."
    else:
        narration = "Working..."
    st.progress(completed / total if total else 0, text=narration)
    summary_parts = []
    for event in events:
        status = event.get("status", "unknown")
        icon = {"done": "✅", "skipped": "⏭️", "error": "❌", "started": "🔄"}.get(status, "•")
        label = PROGRESS_LABELS.get(event.get("step"), event.get("step", "Unknown step"))
        summary_parts.append(f"{icon} {label}")
    st.caption("  ·  ".join(summary_parts))
    if failed:
        st.warning(f"{failed} stage{'s' if failed != 1 else ''} reported an error. See details below.")


def render_usage(usage: list):
    """Render the ChatResponse.usage list (UsageEntry rows) as a table plus
    a total estimated cost, inside the "Cost & performance" expander."""
    if not usage:
        st.caption("No per-call usage data was reported for this turn.")
        return
    import pandas as pd

    df = pd.DataFrame(usage)
    total_cost = df["estimated_cost_usd"].sum() if "estimated_cost_usd" in df.columns else 0.0
    total_tokens_in = df["tokens_in"].sum() if "tokens_in" in df.columns else 0
    total_tokens_out = df["tokens_out"].sum() if "tokens_out" in df.columns else 0
    total_latency = df["latency_seconds"].sum() if "latency_seconds" in df.columns else 0.0
    cols = st.columns(4)
    cols[0].metric("Total est. cost", f"${total_cost:.4f}")
    cols[1].metric("Tokens in / out", f"{int(total_tokens_in)} / {int(total_tokens_out)}")
    cols[2].metric("Total latency", f"{total_latency:.2f}s")
    cols[3].metric("LLM calls", str(len(df)))
    st.dataframe(df, hide_index=True, width="stretch")


def build_export_markdown(turn: dict, index: int) -> str:
    """Render a single finished turn as a standalone Markdown export,
    including the full debate transcript, ticker(s) mentioned in the trail,
    and the final verdict.
    """
    response = turn.get("response") or {}
    lines = [f"# Stock Research & Debate Assistant — Turn {index + 1} export", ""]
    lines.append(f"**User question:** {turn.get('user_message', '')}")
    lines.append("")
    tickers = sorted({e.get("ticker") for e in response.get("trail_events", []) if e.get("ticker")})
    if tickers:
        lines.append(f"**Ticker(s):** {', '.join(tickers)}")
        lines.append("")
    stance = response.get("stance")
    if stance:
        lines.append(f"**Final verdict:** {str(stance).upper()}")
        lines.append("")
    if response.get("final_answer"):
        lines.append("## Final answer")
        lines.append(response["final_answer"])
        lines.append("")
    lines.append("## Debate transcript / reasoning trail")
    for event in response.get("trail_events", []):
        step = event.get("step", "unknown_step")
        status = event.get("status", "unknown")
        ticker = f" ({event.get('ticker')})" if event.get("ticker") else ""
        lines.append(f"### {step}{ticker} — {status}")
        detail = event.get("detail")
        if isinstance(detail, dict):
            text_field = None
            for key in ("argument", "text", "summary", "reasoning", "synthesis", "content"):
                if key in detail:
                    text_field = detail[key]
                    break
            if isinstance(text_field, list):
                lines.extend(f"- {item}" for item in text_field)
            elif text_field is not None:
                lines.append(str(text_field))
            else:
                lines.append(f"```\n{detail}\n```")
        elif detail is not None:
            lines.append(str(detail))
        lines.append("")
    lines.append("---")
    lines.append(NON_ADVICE_DISCLAIMER)
    return "\n".join(lines)


def stream_chat_worker(payload: dict, headers: dict, state: dict):
    """Runs in a background thread — consumes `POST /chat/stream` (real SSE)
    and writes results into `state` (a plain dict, NOT Streamlit calls;
    Streamlit widgets/APIs are not thread-safe to call from a worker thread).
    The main thread's `render_active_stream` fragment polls `state` and does
    all actual rendering.

    Handles the `cancelled` SSE event type the same way as `final`, except it
    also sets `state["cancelled"] = True` so the UI can render it distinctly
    as a partial/stopped turn.
    """
    url = f"{BACKEND_URL}/chat/stream"
    headers = {**headers, "Accept": "text/event-stream"}
    try:
        with requests.post(url, json=payload, headers=headers, stream=True, timeout=(10, 300)) as resp:
            if resp.status_code >= 400:
                try:
                    detail = resp.json()
                except ValueError:
                    detail = resp.text
                state["error"] = f"Backend returned {resp.status_code}: {detail}"
                state["done"] = True
                return
            for raw_line in resp.iter_lines(decode_unicode=True):
                if state.get("stop_reading"):
                    break
                if raw_line is None or raw_line == "":
                    continue
                if raw_line.startswith("event: done"):
                    break
                if not raw_line.startswith("data:"):
                    continue
                data_str = raw_line[len("data:"):].strip()
                if not data_str:
                    continue
                try:
                    item = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                item_type = item.get("type")
                if item_type == "trail_event":
                    state["events"].append(item["data"])
                elif item_type == "final":
                    state["final"] = item["data"]
                elif item_type == "cancelled":
                    state["final"] = item["data"]
                    state["cancelled"] = True
                elif item_type == "error":
                    state["error"] = item["data"]
    except requests.exceptions.RequestException as exc:
        state["error"] = f"Could not reach backend at {url}: {exc}."
    state["done"] = True


@st.fragment(run_every=0.5)
def render_active_stream():
    """Polls `st.session_state.stream_state` (updated by the background
    worker thread) and renders progress/trail live, plus a stop button.

    LIMITATION (Streamlit): a plain `requests.post(..., stream=True)` call
    blocks the script thread it runs on, so a stop button click could never
    reach it if the stream were read synchronously in the main script — the
    script wouldn't be free to notice the click until the read finished. We
    work around this by reading the SSE stream on a background thread and
    using `st.fragment(run_every=...)` to poll shared state and re-render on
    a timer; this keeps the main thread's script free to handle the stop
    button click and fire the cancel POST immediately. The cancel POST is
    fire-and-forget from the frontend's side — the backend must actually
    stop the graph and send a `cancelled` event down the SAME open stream
    for the worker thread to see it and exit its read loop.
    """
    state = st.session_state.stream_state
    if state is None:
        return

    progress_placeholder = st.empty()
    trail_placeholder = st.empty()
    with progress_placeholder.container():
        render_progress_overview(state["events"])
    with trail_placeholder.container():
        render_trail_events(state["events"])

    if not state["done"]:
        stop_col, caption_col = st.columns([1, 4])
        with stop_col:
            if st.button("Stop", key=f"stop_{state['job_id']}", disabled=state.get("cancel_requested", False)):
                state["cancel_requested"] = True
                try:
                    requests.post(
                        f"{BACKEND_URL}/chat/cancel/{state['job_id']}",
                        headers=auth_headers(),
                        timeout=10,
                    )
                except requests.exceptions.RequestException:
                    pass  # best-effort; the poll loop will just keep waiting
        with caption_col:
            st.caption(
                "Cancellation takes effect at the agent's next processing "
                "step, not instantly — you may still see one more step "
                "complete before it stops."
            )
        return

    # Worker finished (naturally or via cancellation) — fold into turns.
    if state.get("error"):
        st.session_state.turns.append(
            {"user_message": state["user_message"], "response": None, "error": state["error"]}
        )
    else:
        final_response = state["final"] or {}
        if final_response.get("risk_tolerance") in _VALID_RISK_PROFILES:
            st.session_state.risk_tolerance_pending = final_response["risk_tolerance"]
        memory_note = final_response.get("memory_note")
        if memory_note:
            st.session_state.memory_note = memory_note
        st.session_state.turns.append(
            {
                "user_message": state["user_message"],
                "response": final_response,
                "error": None,
                "cancelled": state.get("cancelled", False),
            }
        )
    st.session_state.stream_state = None
    st.rerun()


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def process_user_message(user_message: str):
    """Compose the payload (risk tolerance + allocation controls), and kick
    off `POST /chat/stream` on a background thread (see `stream_chat_worker`
    and `render_active_stream`) so the stop button stays clickable while the
    stream is in flight. Shared by the chat form submit and the sample-
    question buttons."""
    composed_message = f"[Sidebar risk tolerance: {risk_tolerance}] {user_message.strip()}"
    if allocation_mode:
        target_text = f" target annual return {allocation_target}%" if allocation_target else ""
        composed_message = (
            f"[Allocation controls: tickers={allocation_tickers or 'from user message'}, "
            f"amount={allocation_amount}, currency={allocation_currency}{target_text}] "
            f"{composed_message}"
        )

    job_id = str(uuid.uuid4())
    payload = {
        "session_id": st.session_state.session_id,
        "message": composed_message,
        "provider": provider or None,
        "model": model or None,
        "api_key": api_key_override or None,
        "job_id": job_id,
    }

    state = {
        "job_id": job_id,
        "user_message": user_message.strip(),
        "events": [],
        "final": None,
        "error": None,
        "cancelled": False,
        "cancel_requested": False,
        "done": False,
    }
    st.session_state.stream_state = state
    thread = threading.Thread(
        target=stream_chat_worker, args=(payload, auth_headers(), state), daemon=True
    )
    thread.start()


st.title("Stock Research App - developed by Edureka Team")
st.caption(
    "Bull vs. bear vs. risk debate, grounded in live price/fundamentals and "
    "news, ending in an explicit judge synthesis. Educational demo only — "
    "not financial advice."
)

tab_chat, tab_what_can_i_ask = st.tabs(["Chat", "What can I ask?"])

with tab_chat:
    trail_container = st.container()
    chat_container = st.container()

    with trail_container:
        st.subheader("Reasoning trail (persistent — grows down the page)")
        if st.session_state.stream_state is not None:
            st.info(f"Streaming agent pipeline for: \"{st.session_state.stream_state['user_message']}\"")
            render_active_stream()
        if not st.session_state.turns:
            st.caption("Ask a question below to see the reasoning trail fill in, or try a sample question:")
            sample_cols = st.columns(3)
            sample_questions = [
                "Should I buy AAPL?",
                "Compare MSFT vs GOOGL",
                "What's Tesla's valuation like?",
            ]
            for col, sample in zip(sample_cols, sample_questions):
                if col.button(sample, key=f"sample_q_{sample}", disabled=not api_key_override):
                    process_user_message(sample)
        for i, turn in reversed(list(enumerate(st.session_state.turns))):
            with st.container():
                st.markdown(f"#### Turn {i + 1}: \"{turn['user_message']}\"")
                if turn.get("error"):
                    st.error(turn["error"])
                    st.divider()
                    continue
                response = turn.get("response") or {}
                if turn.get("cancelled"):
                    st.warning(
                        "⏹️ Stopped early by user — showing what completed "
                        "before cancellation."
                    )
                with st.expander("Agent reasoning steps", expanded=False):
                    render_progress_overview(response.get("trail_events", []))
                    render_trail_events(response.get("trail_events", []))
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
                    st.write(escape_markdown_dollars(final_answer))
                st.caption(f"Disclaimer: {NON_ADVICE_DISCLAIMER}")

                with st.expander("Cost & performance (per-call observability)", expanded=False):
                    render_usage(response.get("usage") or [])

                if response.get("trail_events") or final_answer:
                    st.download_button(
                        "Download this turn as Markdown",
                        data=build_export_markdown(turn, i),
                        file_name=f"debate_turn_{i + 1}.md",
                        mime="text/markdown",
                        key=f"export_md_{i}",
                    )
            st.divider()

    with chat_container:
        st.subheader("Ask a question")

        user_message = st.chat_input(
            'Ask a question, e.g. "Should I invest in AAPL right now?"'
            if api_key_override
            else "Paste your API key in the sidebar to start chatting",
            disabled=not api_key_override,
        )

        if user_message and user_message.strip():
            process_user_message(user_message.strip())

with tab_what_can_i_ask:
    st.markdown(
        """
Here's a plain-English guide to what this assistant is good at, grouped by
the kind of question you're asking. Try any of these phrasings (or your own
version) in the Chat tab.

#### Single-stock analysis
Ask for a full bull vs. bear vs. risk debate on any ticker, grounded in live
price/fundamentals and news, ending in an explicit judge synthesis. You can
also pivot to a different stock mid-conversation, or ask for a fast summary
instead of the full debate.
- *"Should I buy AAPL?"*
- *"What about MSFT instead?"*
- *"Give me a 60-second summary on Tesla."*

#### Debate & critique
Push back on the agents' reasoning — ask why they said something, get the
top-5 reasons to buy or avoid a stock, red-team a thesis, stress-test it, or
check whether a specific news item actually changes the conclusion.
- *"Why did the bull agent say that?"*
- *"What am I missing in this thesis?"*
- *"Am I just looking for confirmation bias here?"*
- *"Does this earnings news actually change the thesis?"*

#### Price & valuation
Ask why a stock's price moved, explore illustrative bear/base/bull "what if"
scenarios (not a computed model), or find out what growth rate is already
priced into the stock (a reverse DCF).

- *"Why did NVDA drop today?"*
- *"What if AAPL grows earnings 15% a year for 5 years?"*
- *"What growth rate is the market already pricing into AMZN?"*

#### Portfolio
Build an allocation across multiple tickers with an investment amount, then
adjust it — add or remove tickers, change target return/risk/horizon,
compare it to an equal-weight allocation, ask for an explanation of the
weights and risk, or stress-test it against a market shock.
- *"Build me a portfolio with $10,000 across AAPL, MSFT, and GOOGL."*
- *"Add NVDA and drop GOOGL from that allocation."*
- *"Compare an equal-weight allocation to what you suggested."*
- *"How would this portfolio hold up in a 2008-style crash?"*

#### What it won't do
This is an educational demo, not a brokerage or advisory service. It will
decline requests for mutual fund recommendations, short-term price
prediction or market timing, options/derivatives/leverage advice, or
placing real trades.
"""
    )
