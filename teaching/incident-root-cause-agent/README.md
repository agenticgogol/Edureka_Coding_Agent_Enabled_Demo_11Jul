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
- `data/jira/tickets.json` — created on first run: local ticket audit store
  (used when real Jira is not configured).

## Run it

From `teaching/incident-root-cause-agent/`, make sure `OPENAI_API_KEY` is
set (this repo's root `.env` already has a verified key — see "API key"
below), then either:

```bash
./run.sh
```

which creates `.venv` and installs requirements on first run if missing,
then starts backend (`http://127.0.0.1:8000`) and frontend
(`http://localhost:8501`) together, or use the `Makefile`:

```bash
make install   # create .venv (python3.11) + install backend/frontend requirements
make seed      # optional, ~1 real embedding call — seed one prior resolved incident
make run       # same as ./run.sh — backend + frontend together
```

or run each piece individually (`make backend`, `make frontend`, each in
its own terminal) if you want separate logs/control. `make help` lists all
targets. API docs are available at `http://127.0.0.1:8000/docs` once the
backend is running.

`langgraph-checkpoint-sqlite` was verified against Python 3.11 — not
checked against 3.13/3.14 in this repo, hence `python3.11` in both
`run.sh` and the `Makefile`.

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

## Real Jira via MCP

The agent can create, comment on, and close real Jira issues through the
open-source `mcp-atlassian` server over stdio. It is enabled only when the
Jira variables below describe a complete credential set; otherwise the local
JSON ticket store remains active.

For Jira Cloud, add these to the repository-root `.env`:

```dotenv
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your.email@company.com
JIRA_API_TOKEN=your_api_token
JIRA_PROJECT_KEY=SCRUM
```

For Jira Server/Data Center, use a personal token instead:

```dotenv
JIRA_URL=https://jira.example.com
JIRA_PERSONAL_TOKEN=your_personal_token
JIRA_PROJECT_KEY=PROJ
```

`JIRA_PROJECT_KEY` must be a project where the account can create and update
issues. `INCIDENT_AGENT_JIRA_ISSUE_TYPE` defaults to `Task`, and
`INCIDENT_AGENT_JIRA_DONE_TRANSITION_NAME` defaults to `Done`; change them if
your Jira project uses different values. The first real Jira operation may
take a moment because `uvx` installs the pinned MCP server package into its
cache. The backend Docker image includes `uv` for the same reason.

The implementation uses `mcp-atlassian>=0.22.0`, which includes the current
patched release for the server's HTTP authentication issue. The application
uses stdio, not the server's HTTP transport, and does not expose the MCP
server port. Never commit `.env` or paste the token into source control.

## GitHub repository scan via MCP

Select **GitHub repository** in the UI to run the separate, read-only GitHub
workflow. Enter `owner/repository` or its GitHub URL, then explicitly check
the authorization box before scanning. The agent reads a bounded set of code
files through GitHub's official MCP server and proposes probable bugs and
unified diffs. It never creates a branch, commit, pull request, or push.

Add a GitHub token to the repository-root `.env`:

```dotenv
GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_...
```

Create it at GitHub → **Settings → Developer settings → Personal access
tokens → Fine-grained tokens**. Give it access only to the repositories you
intend to scan and grant **Contents: Read-only**. Docker must be installed and
required: the application connects directly to GitHub's hosted MCP endpoint
over streamable HTTP and does not require Docker Desktop.

The UI shows findings and patches first. You explicitly select a finding and
confirm Jira creation. After manually applying and pushing/merging the patch,
check the confirmation box; only then does the backend close the Jira ticket.

## Production hardening

Added on top of the original build, per a code-grounded production-readiness
review. Each item below fixes a specific gap that review found — not
generic advice.

### Auth (`backend/auth.py`)

Every route except `/health` now requires an `X-API-Key` header, checked
against `INCIDENT_AGENT_API_KEYS` (comma-separated) in `.env`.
`backend/agent/config.py` fails loudly at import if that var is unset —
same no-silent-degrade policy as `OPENAI_API_KEY`. The Streamlit frontend
sends `INCIDENT_AGENT_API_KEY` (must match one of the backend's keys) on
every call. `run.sh`/`make frontend` export the repo-root `.env` for the
frontend process specifically, since (unlike the backend) it doesn't load
`.env` itself.

### Cost / rate controls (`backend/agent/budget.py`)

- **Per-incident token budget**: `INCIDENT_AGENT_MAX_TOKENS_PER_INCIDENT`
  (default 60,000) caps cumulative LLM token usage for one `start_incident`/
  `resume_incident` call, on top of the existing step ceiling — a stuck
  analysis loop can no longer burn unbounded tokens within that ceiling.
- **Per-key rate limiting**: `INCIDENT_AGENT_RATE_LIMIT_PER_MIN` (default
  10) via a sliding window in `backend/auth.py`'s `verify_api_key`
  dependency. In-memory/single-process — a multi-instance deployment needs
  a shared store (Redis `INCR`/`EXPIRE`) instead, noted inline in the code.
- **Exact-match embedding cache**: the same `incident_text` no longer gets
  embedded twice per submit (once for precedent search, once for storage).

### Retry/backoff (`backend/agent/llm.py`)

Every OpenAI call (`chat_with_tools`, `complete_json`, `embed`) now retries
transient failures (rate limits, timeouts, connection errors, 5xx) with
jittered exponential backoff (via `tenacity`) up to
`INCIDENT_AGENT_OPENAI_MAX_RETRIES` (default 3), plus an explicit client
timeout (`INCIDENT_AGENT_OPENAI_TIMEOUT`, default 60s). A JSON parse
failure from `complete_json` is deliberately NOT retried — the model was
asked for `response_format=json_object`, so that's a real anomaly worth
surfacing, not silently retried.

### Phoenix tracing (`backend/agent/tracing.py`)

Actually wired now, not just config scaffolding — `arize-phoenix-otel` +
`openinference-instrumentation-openai` are in `backend/agent/requirements.txt`,
and `backend/main.py` calls `setup_tracing()` at startup. If
`PHOENIX_COLLECTOR_ENDPOINT` is unset, or the tracing packages aren't
installed, it's a logged no-op — tracing isn't required for the agent to
function, unlike the OpenAI key.

### Sandboxed `run_tests` (`backend/agent/tools.py`)

**What "sandboxing" means here, concretely**: `run_tests` executes a test
file the agent's own patch-drafting step wrote (or a pre-existing synthetic
fixture) via `subprocess`. Before this fix, that subprocess had the full
privileges of the backend process — same filesystem access, same
environment variables (including `OPENAI_API_KEY`), same network access,
no CPU/memory ceiling beyond a 30s wall-clock timeout. A malicious or
buggy test file could read backend secrets, make outbound network calls,
or spin/consume resources on the host.

What's actually implemented (`_sandbox_preexec` in `tools.py`) is
**process-level hardening**, not full container isolation:
- CPU time and virtual-memory rlimits (`RLIMIT_CPU`, `RLIMIT_AS`) so a
  runaway/memory-bomb test gets killed by the OS.
- Process-count limit (`RLIMIT_NPROC`) against fork bombs.
- Core dumps disabled (`RLIMIT_CORE`) so a crash can't write a memory dump
  to disk.
- A scrubbed environment — no `OPENAI_API_KEY`/`PHOENIX_API_KEY`/
  `INCIDENT_AGENT_API_KEYS`/anything matching `API_KEY`/`SECRET`/`TOKEN`/
  `PASSWORD` reaches the child process.
- The existing wall-clock timeout, now configurable
  (`INCIDENT_AGENT_RUN_TESTS_TIMEOUT`).

**What it does NOT do**: block filesystem access outside the repo (the
test still runs as the same OS user), block outbound network calls, or
provide a separate filesystem/PID/network namespace. Each rlimit is
applied best-effort (macOS rejects `RLIMIT_AS` in some configurations —
that's skipped there, not fatal). Real isolation for genuinely untrusted
code needs a container/microVM with `--network=none`, a read-only root
filesystem, and cgroup limits (Docker/gVisor/Firecracker/nsjail) — not
achievable via `resource.setrlimit` alone. That's the upgrade path if this
agent is ever pointed at real, less-trusted repos instead of the fixed
synthetic fixtures.

### Deployment (`Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`)

```bash
docker compose up --build
```

Both images run as a non-root user, expose a real `HEALTHCHECK` (the
backend's now actually checks DB reachability — see `GET /health` below —
not a static payload), and `docker-compose.yml` requires
`OPENAI_API_KEY`/`INCIDENT_AGENT_API_KEYS`/`INCIDENT_AGENT_API_KEY` to be
set (fails to start otherwise, matching the no-mock-mode policy). DB/Jira
runtime state is a named volume (`incident_data`), not baked into the
image or bind-mounted from source.

`GET /health` is deliberately left unauthenticated (container/orchestrator
health checks shouldn't need a key) but now actually queries the incidents
DB and returns `{"status": "degraded", "db": "unreachable"}` if that fails,
instead of a static `{"status": "ok"}` regardless of real health.

### Persistence lifecycle (`scripts/backup_db.sh`, `scripts/prune_checkpoints.py`)

Both SQLite DBs (`incidents.sqlite`, `checkpoints.sqlite`) previously had
no backup or growth-bounding story — `checkpoints.sqlite` in particular
grows one row per graph step forever.

```bash
# Consistent snapshot via `sqlite3 .backup` (not a raw file copy, so a
# backup taken mid-write is never torn). Keeps the last 14 by default.
./scripts/backup_db.sh

# Keep only the most recent checkpoint per thread (safe anytime — the
# approval/resume flow only ever needs the latest to resume; older ones
# are only useful for LangGraph time-travel debugging, unused here).
python scripts/prune_checkpoints.py --compact

# Fully delete checkpoints for incidents that reached a terminal outcome
# more than N days ago (joins via incidents.thread_id — a column added in
# this pass specifically so the two DBs could be joined for lifecycle
# management; pre-existing rows without it are skipped, not guessed at).
python scripts/prune_checkpoints.py --delete-terminal-older-than-days 30
```

Suggested cadence for a real deployment: `backup_db.sh` daily via
cron/systemd-timer, `prune_checkpoints.py --compact` weekly, and
`--delete-terminal-older-than-days` monthly — always back up before
pruning, not after, so a bad prune is recoverable.

### Concurrency (`db.py`, `graph.py`)

Both SQLite DBs (`incidents.sqlite`, `checkpoints.sqlite`) now open with
`PRAGMA journal_mode=WAL` + `busy_timeout=5000` on every connection —
FastAPI's sync routes run each request in a threadpool, so concurrent
`submit_incident`/`approve_incident` calls are real, not theoretical. WAL
mode means readers no longer block the writer, and `busy_timeout` makes a
writer-vs-writer collision retry for up to 5s instead of immediately
raising `database is locked`.

The mocked Jira JSON store (`data/jira/tickets.json`) previously had no
locking at all — concurrent `create_ticket`/`close_ticket` calls for
*different* tickets could race on an unlocked read-modify-write of the
whole file, silently losing whichever write landed second. Fixed with a
lock (`threading.Lock` + best-effort POSIX `flock`) around every mutator,
plus an atomic write (temp file + `os.replace()`) so a crash mid-write
can't leave the file truncated/corrupt. Both fixes are stress-tested in
`tests/test_db.py` (25-30 concurrent writers, zero lost writes).

### Test suite (`tests/`)

```bash
make test
# or directly:
.venv/bin/pytest tests/ -v
```

90 tests across `tools.py`, `graph.py`, `db.py`, `budget.py`, and
`interface.py` — routing logic, the bounded analysis loop (step ceiling,
malformed-output retry, transient-failure retry), path-traversal defenses,
the `run_tests` sandbox (real timeout enforcement, real secret-scrubbing
verification), Jira/incident CRUD + concurrency, and regression tests for
two real bugs found in this session's production-readiness audits (a
token-budget breach during the approve leg losing its audit trail; the
same breach during analysis silently retrying paid calls instead of
stopping). **Zero real API calls** — every LLM/embedding call site is
monkeypatched, and `tests/conftest.py` redirects all DB/Jira state to a
throwaway temp directory (see `INCIDENT_AGENT_JIRA_STORE_PATH` /
`INCIDENT_AGENT_INCIDENTS_DB_PATH` / `INCIDENT_AGENT_CHECKPOINT_DB_PATH` in
`config.py`) so the suite never reads or writes this repo's real demo
data. `requirements-test.txt` (just `pytest`) is dev-only — not installed
in the production Docker images.

### New/changed environment variables

See the root `.env.example` and `backend/agent/config.py` for the full
list. New since the original build: `INCIDENT_AGENT_API_KEYS` /
`INCIDENT_AGENT_API_KEY` (required), `INCIDENT_AGENT_MAX_TOKENS_PER_INCIDENT`,
`INCIDENT_AGENT_RATE_LIMIT_PER_MIN`, `INCIDENT_AGENT_OPENAI_TIMEOUT`,
`INCIDENT_AGENT_OPENAI_MAX_RETRIES`, `INCIDENT_AGENT_RUN_TESTS_TIMEOUT`,
`INCIDENT_AGENT_RUN_TESTS_MAX_MEMORY_MB`,
`INCIDENT_AGENT_RUN_TESTS_MAX_CPU_SECONDS`, `INCIDENT_AGENT_BACKUP_DIR`,
`INCIDENT_AGENT_BACKUP_KEEP`, and the test-isolation path overrides
`INCIDENT_AGENT_JIRA_STORE_PATH` / `INCIDENT_AGENT_INCIDENTS_DB_PATH` /
`INCIDENT_AGENT_CHECKPOINT_DB_PATH` (used by `tests/conftest.py`; leave
unset for normal runs — they default to the real `data/` paths). All have
sensible defaults except the auth keys, which are required.

### Still open (not addressed in this pass)

SQLite (even with WAL) doesn't scale past single-instance/moderate
concurrency — a real high-throughput multi-user deployment would still
need Postgres and async route handlers instead of the current
synchronous-per-request FastAPI routes; WAL mode raises the ceiling, it
doesn't remove it. No prompt-injection-specific defense beyond the
existing "treat file contents as untrusted data" system-prompt
instruction. This repo's eval toolkit (`.claude/skills/`) is the natural
next layer on top of the unit tests above — behavioral/quality evaluation
via `/eval-suite-run integrate`, not just correctness.

## UI features

### Reset history

Sidebar → "⚠️ Reset history" — irreversibly wipes every incident, mocked
Jira ticket, and in-progress approval (including the checkpoint state, so
no stale thread_id can still be resumed after its audit record is gone).
Requires checking "I understand this cannot be undone" before the button
enables — a second gate on top of the backend's own `?confirm=true`
requirement (`DELETE /incidents` rejects a bare request with 400 rather
than treating a missing param as a no-op). Backend: `backend/main.py`'s
`reset_history` route → `interface.reset_all_history()` →
`db.delete_all_incidents()` + `db.delete_all_tickets()` +
`graph.clear_all_checkpoints()`.

### Streaming responses

Checkbox above the submit button: "Stream response (show step-by-step
progress instead of waiting silently)". Same result either way — this
only changes *how* it's delivered:

- **Off (default)**: `POST /incidents` / `POST /incidents/{id}/approve`
  block until the whole graph run finishes, with a generic spinner.
- **On**: `POST /incidents/stream` / `POST /incidents/{id}/approve/stream`
  (Server-Sent Events) stream a human-readable progress line per graph
  node as it completes — "Checking for similar past incidents...",
  "Searching checkout-service for...", "Reading cart.py...",
  "Classified as: code-issue", "Drafting patch...", "Running tests..."
  — shown live in an `st.status()` box, followed by the same result
  payload the blocking route would have returned.

This is **progress streaming** (step-by-step status), not token-level
LLM output streaming — most of what this agent produces (root cause,
diff, ticket) is structured data assembled after a tool call completes,
not free-running prose worth streaming word-by-word, and true token
streaming would have required reworking the OpenAI calls, the
synchronous LangGraph invocation, and the FastAPI↔Streamlit chain end to
end for comparatively little added value here.

**How it works** (`backend/agent/progress.py`, `interface.py`'s
`_stream_call`/`stream_start_incident`/`stream_resume_incident`,
`main.py`'s `/stream` routes): graph nodes call `emit_progress(message)`
unconditionally (a safe no-op when nothing is listening — same contextvar
pattern as `budget.py`). The streaming routes run the existing blocking
`start_incident`/`resume_incident` in a worker thread with a queue-backed
progress sink active, and yield each event over SSE as it arrives,
followed by one final event with the exact result payload the blocking
route would return. No new agent logic — same graph, same budget
scoping, same error handling — only the delivery transport differs.

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
