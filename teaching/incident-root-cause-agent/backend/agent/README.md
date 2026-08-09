# Incident Root-Cause Agent — module interface

Built per `teaching/incident-root-cause-agent/teaching_brief.md` and
`system_design/architecture_design.md`. Single-agent, bounded ReAct
(LangGraph), one structural human-approval interrupt before `apply_patch`.

Framework versions this was built and spike-tested against:
`langgraph==1.2.10` (installed: 1.2.4+ in the repo venv, confirmed
API-compatible), `langgraph-checkpoint-sqlite==3.1.1`. If you upgrade
either package, re-run the spike pattern below before trusting the graph.

## Directory layout

```
teaching/incident-root-cause-agent/
  backend/agent/          <- this module (only thing this build touched under backend/)
    config.py             env/config loading, fails loudly if OPENAI_API_KEY unset
    llm.py                OpenAI chat-with-tools + embeddings wrapper
    repos.py              repo allowlist + path-traversal-safe file access
    db.py                 `incidents` table (audit + precedent store) + mocked Jira JSON store
    tools.py              the 9 tools + OpenAI tool schemas for the search loop
    state.py              AgentState TypedDict (internal only — do not import from the backend)
    graph.py              the LangGraph StateGraph, nodes, interrupt, checkpointer
    interface.py           <-- THE BACKEND IMPORTS ONLY THIS FILE
    seed_data.py           one-time precedent seed script (NOT auto-run — see below)
    requirements.txt
  data/
    repos/checkout-service/       synthetic repo w/ seeded bug (see below)
    repos/auth-service/           synthetic repo, working code
    repos/notifications-service/  synthetic repo, working code
    db/incidents.sqlite            created on first run (audit/precedent store)
    db/checkpoints.sqlite          created on first run (LangGraph checkpointer)
    jira/tickets.json              created on first run (mocked Jira store)
```

## Public interface (`backend/agent/interface.py`)

Import only these three functions from the backend/FastAPI layer:

```python
from backend.agent.interface import start_incident, resume_incident, get_incident_status

# Leg 1: submit an incident, run the analysis leg synchronously.
result = start_incident("checkout API returns 500 on large carts")
# result["status"] is one of:
#   "pending_approval"     -> code-issue path drafted a patch, waiting on human review
#   "resolved_infra"       -> infra-issue, no ticket/patch, informational message only
#   "escalated"            -> step ceiling hit / couldn't determine root cause, honest partial state
# result["thread_id"] identifies this run's checkpoint — save it.

# Leg 2 (only if status == "pending_approval"): approve or reject.
result = resume_incident(thread_id=result["thread_id"], approved=True)
# result["status"] is now one of:
#   "resolved_code_fix"    -> apply_patch -> run_tests passed -> ticket closed
#   "rejected"             -> human said no; ticket stays open with a rejection note
#   "failed_after_retry"   -> post-approval test failure, one draft_patch retry also failed/rejected;
#                              ticket stays open
#   "pending_approval"     -> the one retry path: test failed once, a revised patch was drafted,
#                              and the graph re-entered the SAME interrupt — call resume_incident again

# Read-only poll, does not advance the graph:
status = get_incident_status(thread_id)
```

`start_incident`/`resume_incident`/`get_incident_status` return a flat,
stable dict — no LangGraph node names, no internal `AgentState` keys, ever
leak across this boundary.

## Checkpointer / interrupt contract

- Checkpointer: `langgraph.checkpoint.sqlite.SqliteSaver`, one SQLite file
  at `data/db/checkpoints.sqlite`. `graph.get_checkpointer_cm()` returns
  the context manager; `interface.py` opens it fresh on every call
  (`start_incident`, `resume_incident`, `get_incident_status`) and closes
  it before returning — so nothing needs to keep a live DB connection
  across the (potentially long, indefinite) human-approval wait. This was
  verified against a real process-restart-equivalent scenario in the spike
  script (see "Spike verification" below): open connection, invoke to
  interrupt, close connection, open a brand-new connection against the
  same file, confirm state reloads, resume — this is exactly the pattern
  `interface.py` uses for real.
- There is exactly ONE `interrupt()` call in the whole graph: inside
  `graph.human_approval`, reached only from `code_issue_path` (never from
  `infra_path` or `escalate`). No code path can reach `apply_patch` without
  passing through it and being resumed with
  `Command(resume={"approved": True/False, ...})` — this is a structural
  property of the graph's edges, not a prompt instruction.
- Resume payload shape: `{"approved": bool, "rejection_note": str | None}`.
  `interface.resume_incident(thread_id, approved, rejection_note=None)`
  builds this for you.

## Step ceilings / retries (per `07_loop_engineering.md`)

Implemented in `graph.py`:
- Analysis leg ceiling: 12 tool calls (precedent-check + search/read loop +
  draft_patch + create_jira_ticket all count).
- Execution leg: fixed 3 (`apply_patch`, `run_tests`, `close_jira_ticket`).
- Transient tool/provider failure: 2 retries w/ backoff, inside `analyze`.
- Malformed tool-call output: 1 corrected-prompt retry, inside `analyze`.
- Post-approval test failure: exactly 1 `draft_patch` retry, which
  re-enters the human-approval interrupt (never auto-reapplies a diff).
- Ceiling exceeded / low-confidence: routes to `escalate`, which returns
  an honest "could not confidently determine root cause" message with
  partial findings — never a forced classification or forced patch.

## Untrusted-content delimitation

Incident text is wrapped in `<incident_report>...</incident_report>` and
file contents in `<file_contents path="...">...</file_contents>` (see
`graph.SYSTEM_PREAMBLE` / `tools.draft_patch`) everywhere they enter a
prompt, per `06_context_engineering.md`.

## Path safety

`repos.safe_repo_path` resolves every requested path and verifies it's
still inside the requested repo's own directory (blocks `../` traversal,
absolute-path overrides, and symlink escapes) — enforced in `read_file`,
`run_tests`, and `apply_patch`. Verified in this build's smoke test
(`tools.read_file('checkout-service', '../../../etc/passwd')` raises
`PathEscapeError`).

## Synthetic data

- `checkout-service`: seeded bug in `cart.py` — `calculate_cart_total`
  routes its running total through `_wrap_16bit`, a simulated signed
  16-bit integer wraparound. A cart of 80 items @ $20 x qty 2 overflows
  and wraps to a negative total, which fails
  `assert total_cents >= 0` in `checkout_api.checkout` (-> HTTP 500 in a
  real service). `test_cart.py` currently FAILS against this bug and
  PASSES once the `_wrap_16bit` call is removed — this is exactly the test
  `run_tests` re-executes after `apply_patch`. Confirmed both ways during
  this build (bug present -> 2/3 tests fail; patched -> 3/3 pass).
- `auth-service`, `notifications-service`: working code, own passing
  test suites — used as negative-match repos and for the infra-issue demo
  scenario (the infra path never touches repo files at all).

## What this module does NOT do (out of scope for this build)

- No FastAPI routes, no Streamlit UI — those are built next, against
  `interface.py` only.
- `apply_patch` writes a `.bak` backup alongside the patched file but has
  no automated rollback beyond that (matches `04_tools_and_authorization.md`'s
  "irreversible without an explicit undo step" classification).

## Spike verification already done (no cost)

`interrupt()` + `Command(resume=...)` + `SqliteSaver` reload-after-close
was verified structurally correct with a throwaway spike script (mocked
node logic, no LLM calls) against the installed package versions before
this module was built. All read-only tools (`list_repos`, `search_code`,
`read_file`, `run_tests`, path-traversal blocking, Jira
create/close/reject, `incidents` table insert/read) were smoke-tested
directly, also with no LLM calls.

## NOT yet verified — needs your approval before spending real API $$

The following were written but deliberately NOT executed, per this repo's
"no agent spends real API money without prior approval" rule:

1. **`python -m backend.agent.seed_data`** — seeds one prior resolved
   incident (`checkout-service` / `cart.py` overflow) with a real OpenAI
   embedding, so `search_similar_incidents` has a genuine precedent to
   match on a second demo run. **1 embedding call** (`text-embedding-3-small`),
   effectively free (well under $0.001).
2. **A full end-to-end graph run** (`start_incident(...)` through
   `resume_incident(..., approved=True)`) to prove the analysis loop,
   classification, patch drafting, and post-approval retry all work
   against a real `gpt-4o-mini` model, not just the mocked-logic spike.
   Rough cost: a handful of `gpt-4o-mini` chat calls (tool-calling search
   loop, classification, patch draft) plus 1-2 embedding calls per
   incident run — call it **5-10 gpt-4o-mini calls + 1-2 embedding calls
   per scenario**, on the order of a few cents total for both the code-issue
   and infra-issue happy-path scenarios combined. Recommend running both
   happy-path scenarios from `teaching_brief.md` once real verification is
   approved.

Do not run either of these without the user's explicit go-ahead.
