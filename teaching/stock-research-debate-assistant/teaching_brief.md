# Teaching Brief: Stock Research & Debate Assistant

## Description (as given by user)
A retail investor / student researching one or two specific stocks (US
tickers, and Indian tickers via NSE/BSE suffixes) gets a real bull-vs-bear-
vs-risk debate grounded in fetched price/fundamentals (yfinance), recent
news, and live FX where needed — ending in a judge's explicit Buy/Sell/Hold
stance with reasoning, always paired with a non-advice disclaimer. Supports
single-stock, fundamentals-only, news-driven, risk-fit, two-stock
comparison, and cross-market questions. Multi-turn aware: an orchestrator
classifies each message (new analysis / follow-up / drill-down /
refinement / topic switch / out-of-scope) and only re-runs what's actually
affected. Remembers stated risk tolerance and past ticker analyses across
sessions (SQLite, exact-key lookup, no vector store).

Architecture: see `architecture_design.md` for the full pattern rationale
(supervisor–specialists multi-agent, combining fan-out data-gathering with
adversarial-debate synthesis), tool inventory, memory design, and eval/
security overlays this brief builds from.

## Steps (in order, each builds on the previous)
a) Orchestrator classifies turn type + fans out data fetch (yfinance direct
   + news-search MCP + FX MCP, only the tools the question needs)
b) Bull, bear, and risk agents run a bounded debate (2-3 rounds) grounded
   only in fetched data and any stated risk tolerance
c) Judge synthesizes an explicit Buy/Sell/Hold stance + reasoning +
   non-advice disclaimer
d) Session state persists ticker(s)/fetched data/transcript so follow-up,
   drill-down, and refinement turns reuse it without redundant calls
e) Long-term SQLite memory persists risk tolerance + past ticker syntheses
   across sessions, surfaced unprompted in a new session
f) Streamlit UI shows a live, persistent reasoning trail (stays expanded
   after the answer renders) plus visual data (price chart, fundamentals
   comparison bars, stat cards) alongside the text synthesis

## Format
full_app (streamlit + fastapi) — confirmed: separate FastAPI backend,
Streamlit frontend calling it over HTTP.

## Happy-path test case (user-approved)
1. User opens the Streamlit app, picks a provider/model/API key in the
   sidebar (or confirms the `.env` default), states a risk tolerance
   ("I'm a moderate-risk investor"), then types "Should I invest in AAPL
   right now?" (single-stock, news-driven). The reasoning trail fills in
   live: "Fetching AAPL price/fundamentals... done", "Checking recent
   news... done", "Bull case: ...", "Bear case: ...", "Risk assessment:
   ... (using your stated moderate risk tolerance)", "Judge's synthesis:
   ...". A price trend chart and key-fundamentals stat cards render
   alongside the trail. The final panel shows an explicit Buy/Sell/Hold
   stance with reasoning and a persistent non-advice disclaimer. The full
   reasoning trail remains visible and expanded on screen — it never
   collapses or gets replaced by the final answer.
2. User asks "why did the bear agent say that?" (drill-down) — answered
   instantly from the existing transcript, zero new tool calls, no
   spinner.
3. User asks "Is MSFT overvalued based on its P/E ratio?" (fundamentals-
   grounded, topic switch) — a fresh pipeline runs, but skips the news
   fetch since the question doesn't need it (visible in the trail as a
   skipped step, not a silently-run one).
4. User asks "Compare TCS.NS and INFY.NS for a conservative investor"
   (two-stock comparison, cross-market, risk-fit) — fan-out fetches both
   tickers' data in parallel, FX conversion is invoked only if the
   comparison needs a common currency, fundamentals-comparison bar chart
   renders both tickers side by side, and the risk agent explicitly
   applies "conservative" against the debate.
5. User starts a **brand-new session** (fresh session_id, same app
   instance) and asks about a new stock. Without being reminded, the app
   surfaces a visible "What I remember about you" indicator showing their
   previously stated risk tolerance AND references their prior AAPL
   analysis by name/outcome if relevant (e.g. "last time you were
   bullish on AAPL at a moderate risk tolerance") — proving long-term
   memory (risk profile + historical ticker syntheses) persists and is
   actually used, not just stored.

## Observability
phoenix — user requested tracing wired in to make the multi-agent
fan-out + debate + judge pipeline's LLM calls and tool calls inspectable.

## Vector store
none (architecture design's knowledge & state design: live API/tool data,
not a document corpus — no RAG/vector retrieval involved)

## RAG mode
n/a (no vector store)

## MCP tools
- News search: **`tavily-mcp`** (general web search, npm/stdio) — chosen
  over a stock-ticker-specific news MCP because the orchestrator decides
  open-ended search queries per question type (news-driven, risk-fit
  context, etc.), not just fixed ticker-news lookups. Requires a free
  Tavily API key (`TAVILY_API_KEY`) in `.env` — confirmed/added during
  build via `require-api-key`'s credential-verification discipline.
- FX rate conversion: **Frankfurter Forex MCP** (Python/stdio, wraps the
  free Frankfurter/ECB API) — genuinely no API key required, matching the
  "no key" goal for FX exactly.
- yfinance (price/fundamentals) is NOT an MCP tool — direct deterministic
  Python call, per the architecture design.

## Constraints
- LLM provider key: `ANTHROPIC_API_KEY` (default per architecture design;
  `OPENAI_API_KEY` fallback via `_shared/llm_client.py` if Anthropic key
  absent — Anthropic preferred if both present) — confirmed present via
  `require-api-key`'s real verification call before build starts.
- Streamlit sidebar must let the user choose provider (Anthropic/OpenAI),
  model name, and paste/override the API key at runtime — not just read
  silently from `.env`. This overrides `.env`-only for the session when
  set; `.env` remains the default/fallback if the sidebar is left blank.
- `TAVILY_API_KEY` required in `.env` for the news-search MCP (free tier).
- FX MCP (Frankfurter) needs no API key.
- No paid data sources beyond the LLM call and Tavily's free tier.
- SQLite file for long-term memory (local, no external credential).
- Phoenix observability wired in — traces every agent's LLM call and every
  tool call (yfinance, tavily-mcp, Frankfurter MCP) across the fan-out +
  debate + judge pipeline.
- Non-goals from architecture design apply as hard constraints: no mutual
  funds, no market timing/price prediction, no options/derivatives/
  leverage, no real trading/
  brokerage integration — orchestrator must decline/redirect these, not
  attempt a best-effort answer.
- UI must render data visually (price trend chart, fundamentals comparison
  bars for two-stock questions, key numbers as stat cards) — not raw
  tables/JSON only.
- The step-by-step reasoning trail must remain visible and expanded after
  the final synthesis renders — never collapsed, hidden, or replaced.

## Audience level
intermediate — students/practitioners learning agentic patterns (fan-out +
adversarial debate + turn-type-aware multi-turn state), and retail
investors as the in-story end user.

## Decisions
- The judge's synthesis includes an explicit Buy/Sell/Hold stance +
  reasoning, overriding the original brief's "never directive, always
  pros/cons" non-goal — user's explicit instruction, recorded in
  `architecture_design.md`'s Decision Walkthrough. This is now a
  requirement, not a "your call" default.
- Design process for architecture: one-shot (`agent-architecture-design`),
  not the full 8-stage pipeline — user's choice.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved (full_app: Streamlit + FastAPI)
- Happy-path test case: approved (5-scenario walkthrough above)
- API key verification: verified (ANTHROPIC_API_KEY, claude-haiku-4-5-20251001, real call succeeded)
- Observability: approved (phoenix)
- Vector store: approved (none)
- RAG mode: n/a
- MCP tools: approved (tavily-mcp for news, Frankfurter Forex MCP for FX)
- Ready to generate: approved
- Build: complete (FastAPI backend, Streamlit frontend, root `app.py`
  entrypoint, live data visualizations, and Phoenix/JSON tracing wired)
- Verify: blocked in this sandbox (declared dependencies could not be
  installed because DNS access to PyPI is unavailable; rerun the approved
  live scenarios after installing requirements in a network-enabled
  environment)

## Milestone 2 extension

- Scope: approved portfolio allocation and optimization extension.
- Deterministic owner: `backend/agent/tools/portfolio_optimizer.py` computes
  historical returns, covariance, long-only minimum-variance weights,
  equal-weight comparison, risk contributions, and sector concentration.
- Output requirement: every allocation synthesis shows each ticker's weight
  and currency amount, overall historical annualized return, annualized
  volatility, equal-weight comparison, allocation method, and reasoning.
- Guardrail: weights and metrics never come from the LLM; all figures are
  explicitly historical and not a forecast or guarantee.
- Milestone 2 build: complete
- Milestone 2 verify: blocked in this sandbox (outbound DNS prevents the
  Anthropic live call and localhost binding is restricted); deterministic
  optimizer tests pass and the live run must be repeated from the user's
  terminal.
- Progress/UI refinement: complete — live backend job events are polled by
  Streamlit and the completed reasoning trail remains expanded and persistent.
