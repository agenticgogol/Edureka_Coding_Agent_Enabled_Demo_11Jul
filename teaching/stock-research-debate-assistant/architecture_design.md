# Architecture Design: Stock Research & Debate Assistant (Milestone 1)

## Business outcome

Today a retail investor or student researching a stock gets either (a) a raw
data dump — price, P/E, headlines — with no synthesis, or (b) a generic LLM
opinion with no grounding in real numbers. Neither gives a traceable,
weighed argument they can check. This system fixes that by fetching real
price/fundamentals/news data and running a structured bull-vs-bear-vs-risk
debate grounded only in that data, ending in a judge's synthesis that gives
an explicit Buy/Sell/Hold stance with reasoning — plus every fetched number
and claim traceable back to its source, alongside a persistent non-advice
disclaimer. Success is measured by: does the user get a concrete,
well-reasoned stance they can trace and challenge, not a vague "it depends."

## Decision walkthrough

1. **Q1 (sequence known vs. dynamic) → Dynamic.** Which data-fetch tools run
   depends on question type (a valuation-only question skips news; a
   comparison needs FX only if markets/currencies differ), and turn-type
   classification (new / follow-up / drill-down / refinement / topic-switch)
   changes what runs next per message.
2. **Q2 (high-impact/irreversible?) → No, with a caveat.** No trade is
   executed, no brokerage integration, no money moves — the user still acts
   independently. However, the user explicitly requires the judge to end
   with an **explicit Buy/Sell/Hold stance + reasoning**, not just weighed
   pros/cons (this supersedes the original brief's "never directive" phrasing
   — confirmed with the user; recorded as a Decision below). Because no
   action is taken by the system itself, this does not force a
   human-governance wrapper — but it raises the bar on the disclaimer and
   traceability requirements (see Evaluation & rollout gates).
3. **Q3 (knowledge requirement) → Exact live business data via API.**
   Price/fundamentals via yfinance and news via MCP are live,
   structured/semi-structured per-query fetches — not a static document
   corpus needing citation-style retrieval. Not RAG or Agentic RAG.
4. **Q4 (bounded vs. planner-executor) → Bounded.** Fixed small toolset
   (yfinance, news-search MCP, FX MCP, memory read/write) with a capped
   debate (2-3 rounds). Turn-type classification already determines what
   runs — no separate up-front decomposition stage needed.
5. **Q5 (multi-agent justified?) → Yes.** Bull, bear, and risk must argue
   from genuinely independent, adversarial perspectives — a single agent
   role-playing all three collapses the debate into one voice and loses the
   adversarial tension that makes the synthesis trustworthy. Data-fetch
   calls (price, news, FX) are also independently parallelizable. Per the
   priority order, Q5 = yes takes precedence over Q1/Q4's bounded-ReAct
   result.
6. **Q6 (workload shape) → Short interactive request.** One chat message
   triggers a bounded synchronous pipeline (fetch → debate → synthesize)
   returning within one request/response cycle, streamed live to the UI as
   a reasoning trail.

### Decision: explicit Buy/Sell/Hold stance overrides original non-goal

The original usecase description listed "any directive-style answer... —
always frame as weighed pros/cons" as out of scope. The user has since
explicitly required the judge to give a clear Buy/Sell/Hold call with
reasoning. **This overrides that non-goal.** All other non-goals are
unchanged: no market timing/price prediction, no options/derivatives/
leverage, no portfolio allocation/optimization, no real trading/brokerage
integration. The disclaimer requirement becomes more important, not less,
because the output is now directive — every synthesis must visibly pair the
stance with "not financial advice."

## Chosen architecture pattern

**Supervisor–specialists (multi-agent), combining a fan-out sub-pattern
(parallel data gathering) with an adversarial-debate sub-pattern
(bull/bear/risk → judge).**

```text
                         ┌─────────────────────┐
                         │   User message +      │
                         │   session_id (chat)   │
                         └──────────┬───────────┘
                                    │
                          ┌─────────▼──────────┐
                          │   Orchestrator/      │
                          │   Router agent       │
                          │  (classifies turn    │
                          │   type; picks tools) │
                          └─────────┬──────────┘
              ┌─────────────────────┼──────────────────────┐
              │ new analysis /      │ drill-down /          │ out-of-scope
              │ topic switch /      │ follow-up             │
              │ comparison          │ (reuse session state) │
              ▼                     ▼                       ▼
   ┌────────────────────┐   ┌───────────────┐      ┌────────────────┐
   │  Fan-out data fetch │   │ Answer from   │      │ Decline/redirect│
   │  (parallel, only    │   │ session state,│      │ with reason     │
   │  tools the question │   │ zero new calls│      └────────────────┘
   │  needs):            │   └───────────────┘
   │  - yfinance (price/  │
   │    fundamentals)     │
   │  - news-search MCP   │
   │  - FX MCP (if cross- │
   │    currency)         │
   └──────────┬──────────┘
              ▼
   ┌───────────────────────────────────────────┐
   │      Bounded bull-vs-bear-vs-risk debate    │
   │      (2-3 rounds, grounded only in fetched  │
   │      data + long-term memory risk profile)  │
   │                                              │
   │   ┌────────┐   ┌────────┐   ┌────────────┐ │
   │   │  Bull   │   │  Bear   │   │ Risk agent │ │
   │   │ agent   │   │ agent   │   │ (fit vs.   │ │
   │   │         │   │         │   │ tolerance) │ │
   │   └────┬────┘   └────┬────┘   └─────┬──────┘ │
   │        └─────────────┼───────────────┘        │
   └──────────────────────┼────────────────────────┘
                           ▼
                  ┌─────────────────┐
                  │   Judge agent     │
                  │  synthesizes:     │
                  │  Buy/Sell/Hold +  │
                  │  reasoning +      │
                  │  disclaimer       │
                  └────────┬─────────┘
                           ▼
                  ┌─────────────────┐
                  │  Session state:   │
                  │  ticker(s), fetched│
                  │  data, transcript, │
                  │  refinements       │
                  └────────┬─────────┘
                           ▼
                  ┌─────────────────┐
                  │  Long-term memory │
                  │  (SQLite): risk    │
                  │  tolerance, past   │
                  │  ticker syntheses  │
                  └───────────────────┘
```

Refinement and follow-up turns re-enter this graph at the debate or judge
step only, reusing already-fetched data and the existing transcript rather
than re-running the fan-out.

## Rejected alternatives

- **Bounded single ReAct agent.** Would satisfy Q1 (dynamic) and Q4
  (bounded toolset) alone, but Q5 = yes overrides it: one agent
  role-playing bull, bear, and risk in sequence collapses the adversarial
  structure the brief explicitly requires (distinct, independently-reasoned
  viewpoints, not one voice switching hats).
- **Fixed workflow with no agent judgment at all.** Rejected by Q1 = dynamic
  — a fixed pipeline that always runs price+news+FX regardless of question
  type contradicts the brief's explicit requirement that a valuation-only
  question skip the news fetch, and can't handle turn-type-dependent
  routing (follow-up/drill-down/refinement each need different behavior).
- **RAG / Agentic RAG.** Rejected by Q3 — the knowledge need is live
  structured API data (yfinance, news search, FX), not a static/changing
  document corpus needing citation-style retrieval.

## Knowledge & state design

Per Module 3's taxonomy:
- **Transactional-tool knowledge**: yfinance (price/fundamentals), news
  search MCP, FX MCP — all live, per-query.
- **Curated-context knowledge**: none needed (no fixed policy/prompt corpus
  beyond system prompts per agent role).
- No fine-tuning, no RAG/vector store.

Memory categories in use:
- **Conversation context** — the live message exchange within a session.
- **Task state** — current ticker(s), already-fetched data for them, the
  full current debate transcript, mid-conversation refinements (e.g.
  "assume 5-year horizon"). Held in session state, not a flat message log,
  so follow-up/drill-down/refinement turns can resolve without re-fetching
  or re-debating.
- **Preferences** — stated risk tolerance, persisted long-term (SQLite
  key-value), referenceable unprompted in a brand-new session.
- **Business records** — history of previously analyzed tickers with their
  prior judge synthesis, persisted long-term, exact-key lookup (ticker →
  latest synthesis), no vector store needed.
- **Long-term knowledge / audit history** — not separately modeled beyond
  the above; the debate transcript itself serves as the audit trail for a
  given analysis.

## Tool & side-effect boundaries

Sourcing pass run via `agent-decision-external-tool-sourcing` logic (live
web search performed; see below):

| Tool | Sourcing | Read/Write | Authorization | Idempotency/Audit |
|---|---|---|---|---|
| Price/fundamentals fetch | **Custom (direct yfinance call, not MCP)** — brief explicitly calls for this as a direct deterministic tool since yfinance is a Python library, not a service with an MCP wrapper worth adding indirection for | Read-only | None needed (public market data) | Idempotent; fetched data cached in session state per ticker, logged in reasoning trail |
| News search | **MCP-sourced** — a free public web-search MCP server (e.g. a Tavily-backed or general web-search MCP; exact server pinned during `agent-mcp-real` build, no API key required for the MCP layer itself, though the underlying search provider may need a free-tier key — confirmed against `.env` at build time) | Read-only | None needed (public news) | Idempotent per query; result cached in session state, not re-fetched on follow-up |
| FX rate conversion | **MCP-sourced** — a free public currency-exchange MCP server requiring no API key (e.g. a mid-market-rate MCP server; exact server pinned during build) | Read-only | None needed (public rate data) | Idempotent; cached in session state for the conversation |
| Ticker validity check | **Custom** — folded into the yfinance fetch itself (an invalid/unknown ticker returns no data, which the orchestrator treats as invalid rather than a separate lookup call) | Read-only | None | N/A |
| Long-term memory read/write | **Custom (SQLite)** — no MCP server needed for a local key-value store scoped to this app; a custom tool is the correct choice here, not a gap | Read + Write (append/update only, no deletes in Milestone 1) | Scoped to the requesting user/session identity only | Each write (new synthesis, updated risk tolerance) is naturally idempotent (upsert by ticker/user key); no approval gate needed since it's the system's own working memory, not a shared record |

No tool in this system is high-impact/irreversible (Q2 = No) — no tool
performs a write with real-world consequence outside this app's own memory
store, so no additional approval-gate machinery is required beyond normal
input validation (reject unrecognized/malformed tickers before calling
yfinance).

## Runtime & deployment shape

**Synchronous, short interactive request** (per Q6): one FastAPI request
per chat turn, processed by the orchestrator → (fan-out | state-only) →
(debate | skip) → judge (if new synthesis needed) pipeline, returning a
streamed response so the Streamlit frontend can render the reasoning trail
live (SSE or chunked polling — resolved during `technical-design`).  No
background jobs, no queues, no durable/event-driven execution needed for
Milestone 1 — each request completes within the HTTP request/response
cycle.

## Non-functional budgets & overlays

- **Volume**: teaching/demo scale — single-user or small classroom
  concurrency, not production traffic. No explicit SLO given; target a
  responsive demo (full pipeline, worst case with news+FX, completing in
  well under a minute, with the reasoning trail showing progress so it
  doesn't feel stalled).
- **Cost**: LLM calls per full new-analysis turn: 1 orchestrator
  classification + up to 3 debate agents × up to 3 rounds + 1 judge — kept
  bounded by the loop-engineering step ceiling. No paid data sources
  required; MCP servers and yfinance are free.
- **Security overlay (Tier 6)**: this is a tool-calling system ingesting
  untrusted external content (fetched news text) into LLM context —
  `security-check` must run on the built agent/tool code for prompt
  injection exposure via fetched news content.
- **Guardrails overlay (Tier 7)**: in-scope/out-of-scope classification
  (mutual funds, price prediction, options/derivatives, portfolio
  optimization, real trading) must reliably decline/redirect rather than
  attempt a best-effort answer — this is itself an agentic judgment call
  made by the orchestrator, not a keyword filter, but it should be
  spot-checked against the explicit non-goal list during
  `eval-and-observability`.
- **Cost/latency overlay (Tier 8)**: bounded debate rounds (2-3) and
  bounded tool fan-out are the primary controls; no additional caching
  layer needed beyond per-session already-fetched-data reuse.

## Evaluation & rollout gates

Representative workload for testing: at least one example of every
question type in the brief (single-stock US, single-stock India,
fundamentals-only, news-driven, risk-fit, two-stock same-market comparison,
cross-market comparison with FX, a full multi-turn sequence covering
follow-up/refinement/drill-down/topic-switch, and at least one
out-of-scope request per non-goal category).

Ready-to-ship for this teaching milestone requires:
- Every judge synthesis includes an explicit Buy/Sell/Hold stance, its
  reasoning, and the non-advice disclaimer — verified as always co-present,
  never one without the others.
- Every fetched number/claim in the debate is traceable to a specific tool
  call result in the reasoning trail (no debate agent asserting a fact not
  present in fetched data).
- All 5 turn types are demonstrably handled correctly at least once
  (follow-up resolves a pronoun without re-fetching; drill-down answers
  from transcript with zero new tool calls; refinement re-runs only
  risk+judge; topic-switch starts fresh but still surfaces long-term
  memory).
- A brand-new session references a prior session's stated risk tolerance or
  past analysis unprompted, proving cross-session long-term memory works.
- Every explicit non-goal is declined/redirected, not attempted.

## Architecture-change triggers

- If a future milestone adds actual trade execution or brokerage
  integration, Q2 flips to "Yes" and a human-governance approval wrapper
  becomes mandatory before this pattern can be reused as-is.
- If portfolio-level multi-ticker optimization is added (explicitly
  deferred), that's a new planning/optimization capability that likely
  needs its own planner-executor stage layered in front of this debate
  pattern, not a simple extension of it.
- If news volume/complexity grows to the point where a single search call
  no longer reliably answers "what's the sentiment," revisit Q3a — that
  would push news retrieval toward Agentic RAG-style dynamic
  reformulate/re-check behavior instead of the current single-call fetch.
- If concurrent user volume grows beyond a teaching-demo scale, revisit the
  synchronous runtime shape for queuing/async needs.
