# Incident Root-Cause Triage Agent

A dev/SRE describes an incident in plain English through a Streamlit UI. A
bounded, single-agent LangGraph ReAct agent (backed by a FastAPI service)
checks for a similar past incident first, then searches three synthetic
repos (`checkout-service`, `auth-service`, `notifications-service`) to find
the responsible code and root cause. If it's a code issue, the agent drafts
a patch and a mocked Jira ticket and pauses for human approval before
anything touches disk; once approved, it applies the patch, re-runs the
specific test tied to the incident, and closes the ticket (retrying the
patch once, with a fresh approval pause, if the test fails). If it's an
infra/setup issue, it just tells the user to check with the system admin —
no ticket, no patch, no approval step.

## Architecture

See `system_design/architecture_design.md` for the full pattern rationale
(why single-agent bounded ReAct over multi-agent or a fixed workflow), tool
inventory, memory design (SQLite-backed precedent store, no vector DB),
runtime shape (durable LangGraph checkpointer spanning an indefinite
human-approval pause), and the eval/security overlays (Phoenix tracing,
step ceilings, path-traversal guards).

Component breakdown:
- `backend/agent/` — the LangGraph agent module (built first). Public
  interface: `backend/agent/interface.py` (`start_incident`,
  `resume_incident`, `get_incident_status`). See `backend/agent/README.md`.
- `backend/` — FastAPI service wrapping `backend/agent/interface.py` for
  HTTP. See `backend/README.md` for the exact routes/schemas.
- `frontend/` — Streamlit UI that drives the two-leg submit/approve flow
  against the FastAPI backend.
- `data/repos/` — the three synthetic repos the agent searches.
- `data/db/` — created on first run: `incidents.sqlite` (audit + precedent
  store) and `checkpoints.sqlite` (LangGraph checkpointer).
- `data/jira/tickets.json` — created on first run: mocked Jira ticket store.

## Run it

From `teaching/incident-root-cause-agent/`:

```bash
# 1. Install dependencies (Python 3.11 recommended — this was verified
#    against 3.11; langgraph-checkpoint-sqlite has not been checked
#    against 3.13/3.14 in this repo).
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r frontend/requirements.txt

# 2. Make sure OPENAI_API_KEY is set. This repo's root .env already has a
#    verified, working key — python-dotenv's load_dotenv() walks up from
#    backend/agent/config.py and will find it automatically. No mock mode:
#    the backend fails loudly at import time if the key is missing.

# 3. (Optional, costs ~1 embedding call — needs separate approval) Seed one
#    prior resolved incident so search_similar_incidents has a real
#    precedent to match on a second demo run:
python -m backend.agent.seed_data

# 4. Start the backend (from this directory) — runs on http://127.0.0.1:8000
uvicorn backend.main:app --reload

# 5. In a second terminal (same venv), start the frontend — runs on
#    http://localhost:8501
streamlit run frontend/app.py
```

API docs are available at `http://127.0.0.1:8000/docs` once the backend is
running.

## Try this (happy-path demo scenarios)

Both scenarios are from `teaching_brief.md`'s approved happy-path test case.

**Scenario 1 — code issue.** In the Streamlit UI, type:

> checkout API returns 500 on large carts

The agent (no precedent match on a first run) searches the three repos,
identifies `checkout-service`, reads `cart.py`, and finds the root cause: an
unhandled overflow in the cart-total calculation (`_wrap_16bit` simulates a
signed 16-bit wraparound, which goes negative on a large cart and fails an
assertion). It classifies this as a code issue and shows you the root
cause, the drafted patch, and a mocked Jira ticket, with Approve/Reject
controls — nothing is applied yet. Click **Approve**. The agent applies the
patch, re-runs `test_cart.py`, confirms it passes, and closes the ticket.
The UI shows the final state: patch applied, test result, ticket closed.

**Scenario 2 — infra issue.** Type:

> service unreachable, DNS resolution failing intermittently

The agent classifies this as an infra/setup issue and shows an
informational message recommending you check with the system admin — no
ticket, no patch, no approval step.

## API key

`OPENAI_API_KEY` is required (used for both the `gpt-4o-mini` reasoning
model and `text-embedding-3-small` embeddings for precedent search). This
repo has no mock mode anywhere — a missing or broken key fails loudly at
backend import time, it does not silently degrade. The key is already
present in this repo's root `.env` and was verified working with a real
call earlier in this session (see `teaching_brief.md`'s checkpoint status).

## Verified (real end-to-end run)

Both happy-path scenarios were driven through the real running backend
(seed → `POST /incidents` → `POST /incidents/{thread_id}/approve` →
`GET /incidents`) against the live OpenAI API, with the user's explicit
approval for the spend (~$0.05, actual usage a fraction of that: 1 seed
embedding call + ~10 `gpt-4o-mini`/embedding calls across both scenarios).

- **Seed**: `python -m backend.agent.seed_data` — succeeded, 1 real
  embedding call, seeded `checkout-service`/`cart.py` precedent.
- **Scenario 1 (code issue)**: submit → correctly identified
  `checkout-service`/`cart.py`, correct root cause (16-bit wraparound
  overflow on large carts), valid patch removing `_wrap_16bit`, ticket
  drafted, `status: pending_approval`. Approve → patch applied, all 3
  tests in `test_cart.py` passed (`test_large_cart_total_is_not_negative`,
  `test_large_cart_checkout_does_not_500`, `test_small_cart_still_works`),
  ticket closed, `status: resolved_code_fix`.
- **Scenario 2 (infra issue)**: submit → correctly classified as
  `infra-issue`, informational message recommending a system-admin check,
  no ticket, no patch, `status: resolved_infra`.
- **Audit history**: `GET /incidents` returned all 3 records (seed +
  both scenarios) with correct fields.
- **Precedent match**: did *not* fire on Scenario 1 despite a
  near-duplicate seeded incident — `search_similar_incidents` (confirmed
  correctly wired as the graph's automatic entry node, not an
  LLM-discretionary tool call) returned a cosine similarity below the
  `PRECEDENT_SIMILARITY_THRESHOLD = 0.80` cutoff in
  `backend/agent/tools.py`, because the two incident descriptions are
  phrased quite differently ("checkout API returns 500 on large carts" vs.
  the seed's more detailed multi-sentence description). This is not a
  wiring bug — the agent still reached the correct answer via full search
  either way — but the threshold is worth tuning down (e.g. to ~0.6-0.7)
  or the seed data rephrased closer to realistic incident-report brevity,
  if a live demo specifically wants to showcase the precedent-shortcut
  path firing on the first try.

Verified against: OpenAI (`gpt-4o-mini` for reasoning, `text-embedding-3-small`
for precedent similarity), no vector store (in-process cosine similarity
over SQLite-stored embeddings), Python 3.11 venv at `.venv/`.
