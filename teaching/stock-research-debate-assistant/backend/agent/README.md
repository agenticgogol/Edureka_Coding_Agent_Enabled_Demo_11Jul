# Agent/graph layer — stock-research-debate-assistant

Implements the supervisor-specialists (fan-out + adversarial debate)
LangGraph topology described in `architecture_design.md`. The backend
should import **only** `run_turn` from this package (`backend.agent`) —
no internal node/state shape is meant to leak across that boundary.

## Entry point

```python
from backend.agent import run_turn

result = run_turn(
    session_state,       # dict from the previous call, or None for a new session
    user_message,        # str
    user_key="alice",    # stable identity for long-term-memory lookups
    provider=None,       # optional sidebar override, e.g. "anthropic"
    model=None,          # optional sidebar override, e.g. "claude-haiku-4-5-20251001"
    api_key=None,        # optional sidebar override
)
# result = {
#   "session_state": {...},        # pass back in on the next call
#   "final_answer": "...",
#   "stance": "Buy" | "Sell" | "Hold" | None,
#   "new_trail_events": [ {step, ticker, status, detail}, ... ],
#   "memory_note": "..." | None,
# }
```

`session_state` is an opaque dict — store and pass it back verbatim per
chat session (e.g. in an in-memory dict or a session table keyed by
`session_id`). It holds `tickers`, `fetched_data`, `fx_data`,
`risk_tolerance`, `refinements`, `transcript`, and `trail`.

## Graph topology

```
START -> orchestrator
  -> out_of_scope        -> decline -> END
  -> no ticker resolved  -> invalid_ticker -> END
  -> drill_down          -> drill_down_answer -> END   (zero new tool calls)
  -> follow_up           -> follow_up_answer -> END    (zero new tool calls)
  -> refinement          -> risk_refine -> judge -> END (no re-fetch, no bull/bear rerun)
  -> new_analysis / topic_switch / comparison
       -> Send-fan-out: fetch_price (per ticker, always)
                         fetch_news (per ticker, only if orchestrator selected it)
                         skip_news (once, if news wasn't selected — visible in trail)
       -> (join barrier) -> fetch_fx (derives currency pair from what
          fetch_price actually returned; self-skips if only one currency
          is present, visible in trail either way)
       -> debate (bounded 2-round bull/bear/risk, see nodes/debate.py)
       -> judge -> END
```

No LangGraph checkpointer is used — there's no human-in-the-loop
interrupt/resume requirement here (Q2 = No in the architecture design).
`run_turn` is invoked once per HTTP chat turn with the previous turn's
full state as the graph's initial state; `state.py`'s reducers
(`_merge_dicts` for `fetched_data`/`fx_data`, `operator.add` for
`transcript`/`trail`) handle correctly accumulating/merging across both
the same turn's parallel fan-out and across turns, without needing
LangGraph's own persistence layer.

## Debate round count (documented per the brief's requirement)

`nodes/debate.py`'s `ROUNDS = 2`:
- Round 1: bull opens, bear opens, risk gives its initial fit assessment.
- Round 2: bull rebuts bear's round-1 argument; bear rebuts bull's
  round-1 argument. Risk does not get a rebuttal round in Milestone 1.

This is implemented as an actual loop (`if ROUNDS >= 2: ...`), not
copy-pasted calls, so raising the round count later is a one-line change.

## MCP servers (verified live on 2026-08-29, see tool docstrings)

- **News search** — `tavily-mcp` (npm, published by tavily-ai). Stdio
  launch: `npx -y tavily-mcp` (no version pin, per Tavily's own docs —
  pinning a specific version drifts stale fast). Requires `TAVILY_API_KEY`
  in the subprocess env. The client discovers the exposed
  `tavily-search`/`tavily_search` tool name before calling it.
- **FX rates** — `frankfurtermcp` (PyPI, anirbanbasu). Install:
  `pip install frankfurtermcp`. Stdio launch: `python -m
  frankfurtermcp.server` with `MCP_SERVER_TRANSPORT=stdio` set explicitly.
  No API key required. Tool used: `convert_currency_latest`.

The MCP wrappers call the discovered news tool with the conventional
`{"query", "max_results"}` arguments and call the FX tool with
`{"amount", "from_currency", "to_currency"}`. A protocol mismatch remains
a hard, visible error; it is never converted into fabricated news or FX
data.

## Memory (`memory.py`)

SQLite-backed, DB file at `backend/data/memory.db` (created on first use).
Four functions only, per spec: `get_risk_tolerance`, `save_risk_tolerance`,
`get_past_analysis`, `save_analysis` — both writes are upserts (no
deletes). `run_turn` already calls these (loading a stored risk tolerance
at session start, detecting a stated risk-tolerance mention in the
message, and looking up/saving per-ticker analyses) so the backend does
not need to reimplement that logic — it only needs to persist
`session_state` across turns.

## Estimated cost/calls for one full end-to-end test run

For a single **new_analysis** turn (worst case, with news + no FX needed):
- LLM calls: 1 (orchestrator) + 5 (debate: bull, bear, risk, bull-rebuttal,
  bear-rebuttal) + 1 (judge) = **7 LLM calls**, all short prompts on
  `claude-haiku-4-5-20251001` (cheap, confirmed-reachable model).
- Tool calls: 1 yfinance call (free, local) + 1 tavily-mcp search (1 call
  against the free Tavily tier).
- A **comparison** turn (2 tickers) roughly doubles the yfinance calls and
  runs the debate/judge once against both tickers' combined data (same
  LLM call count as above, not doubled, since bull/bear/risk each argue
  once about the whole comparison).
- **drill_down**/**follow_up** turns: 1 LLM call, 0 tool calls.
- **refinement** turns: 2 LLM calls (risk + judge), 0 tool calls.
- **out_of_scope**: 1 LLM call (orchestrator only), 0 tool calls.

A full 5-scenario happy-path run (per the brief) would be roughly
**~20-25 LLM calls total** and **2-4 yfinance/tavily-mcp/Frankfurter tool
calls**, all on the free/cheap tiers already confirmed present — but per
this repo's cost-approval rule, do not run this live without the user's
go-ahead first.

## Known limitation flagged for the backend-builder

`memory.get_past_analysis` is an exact ticker-key lookup (per the
architecture design's explicit choice — no vector store, no "most
recent ticker for this user" query). Surfacing "last time you asked about
X" in a brand-new session (test scenario 5) therefore requires the
backend to know which ticker to check — `run_turn` checks
`get_past_analysis` for whatever ticker(s) the *current* message resolves
to, and also surfaces stored risk tolerance unprompted via `memory_note`
on turn 1 of a session. If the product needs "surface my single most
recent ticker ever, with zero new input," that needs an additional
small table (e.g. `last_ticker_by_user`), which is out of this module's
scope per the memory interface spec given.
