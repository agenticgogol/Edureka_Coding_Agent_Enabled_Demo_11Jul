# Teaching Brief: Incident Root-Cause Triage Agent

## Description (as given by user)

A dev/SRE submits a free-form incident description via a Streamlit UI. The system determines which of 3 synthetic repos (checkout-service, auth-service, notifications-service) is responsible, analyzes the repo's code alongside the incident description to find the root cause, and branches: for a code issue, it drafts a mocked Jira ticket and a proposed patch, pausing for human-in-the-loop approval before the patch is ever applied; for an infra/setup issue, it informs the user and recommends checking with the system admin instead. Once a patch is approved and applied, the system re-runs the specific synthetic test(s) tied to the incident and closes the ticket on a pass. Before searching, the agent first checks a store of past incidents for a similar precedent — if found, it skips straight to the known repo/file rather than re-searching, but still independently re-derives the actual code fix itself. Built as a **single-agent, bounded ReAct agent** (LangGraph) — chosen over multi-agent because there's no measurable parallelism or isolation need (every step is the same search-and-read reasoning), and over a fixed workflow because which repo/file is responsible is genuinely unknown up front and must be discovered via search.

Architecture: see `system_design/architecture_design.md` for the full pattern rationale, tool inventory, memory design, and eval/security overlays this brief builds from.

## Steps (in order, each builds on the previous)

a) Precedent check — `search_similar_incidents` against the seeded incident history (in-process embedding similarity over SQLite); if a strong match exists, carry its identified repo/file forward as a starting point.
b) Repo/root-cause search — `list_repos`, `search_code`, `read_file` across the 3 synthetic repos until the responsible file(s) and root cause are found (or the step ceiling is hit).
c) Classification — code-issue vs. infra-issue.
d) Code-issue path — `draft_patch` + `create_jira_ticket` (mocked), then a hard interrupt: pause for human approval before anything is written to disk.
e) Infra-issue path — inform the user directly, recommend checking with the system admin; no ticket, no patch.
f) Post-approval — `apply_patch` → `run_tests` (the specific synthetic test(s) tied to the incident) → `close_jira_ticket` on pass; on a test failure, one `draft_patch` retry that re-enters the approval interrupt (never auto-reapplied); on rejection, the loop ends with the ticket left open and a rejection note.

## Format

full_app (streamlit + fastapi)

*(Pre-filled from architecture design: stage 3 chose a durable/checkpointed runtime spanning an indefinite human-approval pause, which needs a real backend process and persisted state — not expressible as a single notebook. Frontend/backend split (Streamlit UI, separate FastAPI backend) was confirmed during Step 2 clarification of `/agent_system_design_to_build_onego`, before architecture design ran.)*

## Happy-path test case (draft, not yet approved)

**Scenario 1 (code issue):** The user opens the Streamlit app and types: "checkout API returns 500 on large carts." The agent (no precedent match on first run) searches the 3 repos, identifies `checkout-service`, reads its code, finds the root cause (e.g. an unhandled overflow/edge case in cart total calculation), classifies it as a code issue, and shows the user: the root cause explanation, a mocked Jira ticket, and a proposed patch — with an "Approve" / "Reject" control, nothing applied yet. The user clicks Approve. The agent applies the patch, re-runs the specific test tied to this incident, sees it pass, and closes the ticket. The UI shows the final state: root cause, patch applied, test result, ticket closed.

**Scenario 2 (infra issue):** The user types: "service unreachable, DNS resolution failing intermittently." The agent classifies this as an infra/setup issue and shows the user an informational message recommending they check with the system admin — no ticket, no patch, no approval step.

## Observability

phoenix

*(Pre-filled from architecture design stage 8: full step/tool tracing with cost/latency, plus alerts on step-ceiling hit rate, any un-approved apply_patch attempt, and post-approval test-failure rate — uses this repo's `eval-and-observability` default, Phoenix with local fallback.)*

## Vector store

none

*(Pre-filled from architecture design stage 5: precedent search uses in-process cosine similarity over embeddings stored as a column in the same SQLite `incidents` table — explicitly chosen over a dedicated vector DB given the demo's single-digit-incidents-per-session scale.)*

## Constraints

- `OPENAI_API_KEY` required (reasoning/orchestration model + embedding calls for precedent search) — no mock mode, per this repo's standing rule.
- No real Jira/GitHub/PagerDuty integration — Jira is a local mocked JSON store; incident intake is Streamlit free-text only, no external incident-source integration.
- No auth/multi-tenant support — single-user demo.
- No production deployment target.
- No paid tools beyond the OpenAI LLM + embedding calls themselves — all repo search, test running, and ticketing are local/custom, per architecture stage 4.
- SQLite is the persistence layer for both the LangGraph checkpointer (task/scratch state across the approval interrupt) and the `incidents` table (audit history + precedent store) — both must survive a backend process restart.

## Audience level

intermediate — this demo is built to illustrate a realistic bounded-ReAct-agent-with-HITL pattern (precedent lookup, dynamic multi-file code search, human-approval interrupt, post-approval re-validation), not an introductory single-tool-call example.

## Decisions

- Precedent-cache capability (checking historical incidents before full search) was added by explicit user request mid-design, after the initial architecture draft had excluded a long-term-knowledge/retrieval component entirely. This reversed stage 5's original "long-term knowledge: not needed" call — see `system_design/05_memory.md`'s revision note for the full reasoning.
- The user confirmed a precedent match should only shortcut repo/file *identification* — the agent must still independently derive the actual root cause and patch content itself, never reuse a past patch verbatim.

## Checkpoint status

- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (OpenAI, gpt-4o-mini, real call succeeded)
- Observability: approved
- Vector store: approved
- Ready to generate: approved
- Build: complete
- Verify: complete
