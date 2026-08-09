# Architecture Design: Incident Root-Cause Triage Agent

## Business outcome

The underlying need is to compress the manual debugging judgment of an experienced senior software engineer — reading an incident report, figuring out which service/repo is responsible, tracing the root cause in code, and deciding whether it's a code bug or an infra/setup problem — into an agent that can do this confidently over a real codebase, propose a fix, and prove the fix works, with a human still approving before any code changes take effect. Framed explicitly by the user as a demo of an agent aiming to replace the need for an experienced senior engineer's debugging judgment, not just do shallow keyword matching. (Source: `01_agent_topology.md`)

## Decision walkthrough

Full Q&A for each stage lives in its own file; summarized here in order:

1. **Topology** (`01_agent_topology.md`): known workflow steps, one irreversible action (patch write), bounded tool space, no measurable parallelism/isolation need → **single-agent**.
2. **Design pattern** (`02_design_pattern.md`): no external knowledge base, dynamic search over local files, bounded toolset → **bounded ReAct agent**.
3. **Runtime shape** (`03_runtime_deployment_shape.md`): short synchronous legs around an indefinite human-approval wait, user-triggered, single-item, must survive restarts → **user-request-triggered, durable/checkpointed synchronous legs**.
4. **Tools & authorization** (`04_tools_and_authorization.md`): 8 custom/local tools (revised to 9 mid-process — see below), one irreversible tool (`apply_patch`) gated on human approval.
5. **Memory** (`05_memory.md`, revised mid-process): checkpointed task state (SQLite) + a shared `incidents` table doubling as audit history and a similarity-searchable precedent store (in-process embeddings, no vector DB).
6. **Context engineering** (`06_context_engineering.md`): small fixed preamble, everything else on-demand and narrow; structured-note-taking pruning across the approval-wait resume; untrusted content flagged for delimitation.
7. **Loop engineering** (`07_loop_engineering.md`): step ceiling 12 (analysis) + 3 (execution) = 15; six termination conditions including honest incompleteness; one HITL interrupt at `apply_patch`.
8. **Eval/security/guardrails** (`08_eval_security_guardrails.md`): structural interrupt as primary injection defense, rule-based + narrow LLM-judge eval, full-trace observability, budget check passed with no conflicts.

**Mid-process revision**: after stage 5's first draft, the user requested a precedent-cache capability — check whether a similar past incident exists before doing full repo/file search, to save that cost, while still independently re-deriving the actual fix. This added `search_similar_incidents` to stage 4's tool inventory and reversed stage 5's original "long-term knowledge: not needed" call. Stages 1-3 were unaffected (confirmed no conflict); stages 4 and 5 were revised and re-approved before stages 6-8 ran, so the design below already reflects the precedent-cache capability throughout — there is no unresolved inconsistency between stages.

## Chosen architecture pattern

**Single-agent, bounded ReAct.**

```text
                         ┌─────────────────────────────┐
                         │   Streamlit UI (free text)   │
                         └───────────────┬───────────────┘
                                         │ incident description
                                         ▼
                         ┌─────────────────────────────┐
                         │        FastAPI backend        │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────┐
                 │         Bounded ReAct Agent (LangGraph)     │
                 │                                              │
                 │   [search_similar_incidents]  (read, first)  │
                 │              │                               │
                 │              ▼                               │
                 │   [reason] ──▶ [list_repos / search_code]     │
                 │      ▲              │                        │
                 │      │              ▼                        │
                 │      └──────── [read_file]     (read)        │
                 │      ▲              │                        │
                 │      │              ▼                        │
                 │      └──── classify: code-issue | infra-issue │
                 │                      │                        │
                 │         ┌────────────┴────────────┐           │
                 │         ▼                          ▼          │
                 │  [draft_patch +           [inform user:        │
                 │   create_jira_ticket]        infra/admin]       │
                 │         │                                      │
                 │         ▼                                      │
                 │  ═══ INTERRUPT: human approval ═══              │
                 │         │ approved          │ rejected          │
                 │         ▼                    ▼                  │
                 │  [apply_patch]        end, ticket stays open,    │
                 │         │             rejection note recorded    │
                 │         ▼                                      │
                 │  [run_tests] ──fail──▶ 1 retry: [draft_patch]    │
                 │         │ pass              (re-enters interrupt)│
                 │         ▼                                      │
                 │  [close_jira_ticket]                            │
                 └───────────────────────────────────────────┘
```

## Rejected alternatives

- **Multi-agent** (e.g. separate locator/analyst/patch-writer agents) — rejected: no measurable parallelism or isolation need (stage 1, Q4/Q5 both "no"); would only add handoff overhead for what is one continuous reasoning-plus-tool-use task.
- **Fixed workflow (no tool loop)** — rejected: repo identification is itself dynamic (no repo hint given), so a fixed sequence can't express "keep searching until you find the culprit" (stage 2).
- **Planner-executor** — rejected: no real subtask dependencies requiring up-front decomposition; every step is the same search-and-read primitive the ReAct loop already handles iteratively (stage 2).
- **Plain synchronous request/response for the whole flow** — rejected: can't block one HTTP connection through an indefinite human-review wait (stage 3).
- **Fire-and-forget async (no restart survival)** — rejected: violates the explicit persisted-incident-history requirement; a restart during an approval wait would lose the pending patch (stage 3).
- **Dedicated vector database for precedent search** — rejected: at this demo's scale (single-digit incidents per session), in-process cosine similarity over stored embeddings in the same SQLite table is simpler and equally correct; a full vector DB is infrastructure the demo doesn't need (stage 5).

## Runtime & deployment shape

(Verbatim from `03_runtime_deployment_shape.md`)

User-request-triggered, durable/checkpointed synchronous legs around an indefinite human-approval pause:
- **Leg 1 (sync):** POST incident → agent runs precedent-check/search/analyze/classify/draft → graph hits the `apply_patch` interrupt → returns "pending approval" immediately. State checkpointed at this pause point.
- **Pause (durable, unbounded duration):** state sits checkpointed until a human acts; survives a FastAPI restart because the checkpoint is on disk (SQLite), not in-process.
- **Leg 2 (sync):** POST approve/reject → graph resumes from checkpoint → (approved) apply_patch → run_tests → close ticket → return result; (rejected) end, ticket stays open.

## Tool & side-effect boundaries

(Verbatim tool inventory from `04_tools_and_authorization.md`, including the mid-process revision)

| Tool | Sourcing | Read/Write | Reversible? | Auth tier | Idempotent? | Audited? |
|---|---|---|---|---|---|---|
| `search_similar_incidents` | Custom | Read | n/a | No gate | Yes | Yes |
| `list_repos` | Custom | Read | n/a | No gate | Yes | No |
| `search_code` | Custom | Read | n/a | No gate | Yes | No |
| `read_file` | Custom | Read | n/a | No gate | Yes | No |
| `run_tests` | Custom | Read + local execution | n/a | No gate | Yes | Yes |
| `draft_patch` | Custom | Read (proposal only) | n/a | No gate | Yes | Yes |
| `create_jira_ticket` (mocked) | Custom | Write | Reversible | Service-scoped, no approval | Yes | Yes |
| `apply_patch` | Custom | Write | **Irreversible** | **Human approval required** | Yes | Yes — mandatory |
| `close_jira_ticket` (mocked) | Custom | Write | Reversible | Service-scoped, no approval | Yes | Yes |

All tools are custom/local — no external sourcing was needed (no real Jira/GitHub/PagerDuty integration, per non-goals).

## Knowledge & state design

(Verbatim per-category table from `05_memory.md`, revised version)

| Category | Needed? | Store type | Scope / TTL |
|---|---|---|---|
| Conversation context | Yes, minimal | In-context (LangGraph message/state list) | Per-task-instance |
| User preferences | Not needed | — | — |
| Task/scratch state | Yes | LangGraph SQLite checkpointer | Per-task-instance, until terminal state |
| Business records | Yes | Existing synthetic repo files + mocked Jira JSON | Long-lived |
| Long-term knowledge | Yes (reversed from initial draft) | Shared SQLite `incidents` table, in-process embedding similarity | Long retention |
| Audit history | Yes | Same `incidents` table (double-duty with long-term knowledge) | Long retention, no TTL |

A matched precedent only shortcuts the repo/file *search* step — the agent still independently reads files and derives its own root cause and patch; it never reuses a past patch verbatim.

## Context engineering

(Summarized from `06_context_engineering.md`)

- **Always in context**: role/instructions, code-vs-infra classification rubric, all 9 tool schemas, the explicit apply_patch-requires-approval rule, current incident text.
- **On-demand**: best-matching precedent summary (not the full table), one file's contents at a time, task-state summary on resume.
- **Never direct**: full audit table, bulk repo contents, raw step-by-step tool-call transcripts.
- **Pruning strategy**: structured note-taking — on resume after the approval wait, the model gets a compact distilled summary (identified repo, root cause, evidence excerpts, drafted patch), not a full replay.
- **Untrusted content**: incident text and file contents both flagged; must be explicitly delimited (`<incident_report>`, `<file_contents>`) and are carried forward as a security check.

## Loop engineering

(Verbatim from `07_loop_engineering.md`)

- **Step ceiling**: 12 (analysis leg) + 3 (execution leg) = 15 total.
- **Termination conditions**: infra resolution; code-issue drafted awaiting approval (not terminal); approved patch + tests pass → closed; approved patch + tests fail → one retry, re-enters approval; patch rejected → ends, ticket open; ceiling exceeded → honest escalation.
- **Retry policy**: 2 retries w/ backoff for transient tool failures; 1 corrected-prompt retry for malformed tool calls; 1 `draft_patch` retry for post-approval test failure (never auto-reapplied).
- **HITL interrupt**: exactly one, at `apply_patch`, cross-checked against stage 4's tool table with no gaps.
- **Ceiling-exceeded behavior**: explicit "could not confidently determine root cause" escalation with partial state — never a forced guess.

## Non-functional budgets & overlays

(From `08_eval_security_guardrails.md`)

**Security**: `apply_patch`'s structural graph interrupt is the primary defense against prompt injection from incident text or code content — the model cannot reach it without a separate human-approval event, regardless of injected instructions. `create_jira_ticket`/`close_jira_ticket` carry acceptable low residual risk (mocked local records). No query is built by unsafe string concatenation; `apply_patch`/`read_file` are restricted to the 3 known repo directories. Recommend running `security-check` against the built code to verify the interrupt can't be bypassed and file paths can't traverse outside the allowlisted repos.

**Guardrails**: explicit delimitation of incident text and file contents in the prompt; structured-output schema validation on drafted patches before showing them for approval; never narrate a patch as "applied" unless the interrupt structurally fired. Failure behavior is always a user-visible, honest message — never silent blocking.

**Cost/latency budget check**: stage 3's ceiling (single-user, single-digit incidents per session, no hard SLO, no formal cost ceiling beyond this repo's per-call approval rule) is consistent with the assembled design — single model, single-agent loop capped at 15 tool calls, one embedding call per incident. No conflict found.

## Evaluation & observability

**Evaluation**: ~9-12 synthetic golden incidents across the 3 repos, covering code/infra/ambiguous cases and both precedent-match and no-precedent paths. Mostly rule-based judging (exact match on repo/classification; `run_tests` itself as the patch-validity judge); narrow LLM-as-judge only for root-cause explanation quality; human review sampled specifically on the `apply_patch` path. Re-eval on every deploy plus any prompt/tool/precedent-data change.

**Observability**: every LLM and tool call traced with latency/cost; full step sequence per incident; whether a precedent was matched and used; human-approval wait duration. Alerts on: step-ceiling hit rate, any `apply_patch` attempted without a recorded approval (should be structurally impossible — critical bug if it fires), post-approval test-failure rate. Backend: this repo's `eval-and-observability` default (Phoenix, local fallback).

## Architecture-change triggers

- **Volume growth beyond single-user/single-digit-incidents-per-session** (stage 3) would require revisiting the runtime shape — likely moving from a single FastAPI process with a local SQLite checkpointer toward a proper job queue and a shared Postgres-backed checkpointer, and possibly the deployment shape overall.
- **A new tool with a higher auth tier than "human approval required"** (e.g. an action affecting a real production system, real Jira/GitHub) would require revisiting stage 4's authorization rubric and potentially stage 8's security posture — the current design's security model leans heavily on `apply_patch` being the *only* irreversible action; a second irreversible tool would need its own independently-justified gate, not an assumption that the existing interrupt covers it.
- **A repeated step-ceiling breach in real usage** (stage 7's alert) would justify revisiting either the ceiling itself or, more fundamentally, whether bounded ReAct is still the right pattern — persistent ceiling breaches could indicate the search space has grown beyond what a single bounded loop can reliably cover, at which point planner-executor (rejected at stage 2 for the current scale) might become the better fit.
- **Any real external system replacing the mocked Jira client** would require re-running `agent-decision-external-tool-sourcing` for that tool specifically, since it would newly need real sourcing (free/paid/alternative) that wasn't needed while it was a local mock.

## Status: APPROVED (assembled from 8 approved stage files)
