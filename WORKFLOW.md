# Workflow — which skill or subagent to invoke, and when

This is the canonical reference for building anything in this directory.
`CLAUDE.md` has the short version; this file has the full table and the
reasoning behind the ordering.

## How invocation actually works (read this first)

Three different mechanisms are in play, and they trigger differently:

- **Skills** (`.claude/skills/*/SKILL.md`) are auto-discovered by Claude
  Code from their `description` field. Claude *may* invoke one on its own
  when a task matches, but it is not required to, and it can also be
  invoked explicitly by name ("use the `security-check` skill"). Do not
  rely on a skill firing itself for anything that must happen — treat
  skills as capabilities the agent draws on, not as a scheduler.
- **Subagents** (`.claude/agents/*.md`) never run themselves — something
  has to spawn them (the `Agent` tool) or address them directly. They
  exist to isolate context per slice (frontend vs backend vs agent code),
  not to enforce sequencing on their own.
- **Slash commands** (`.claude/commands/*.md`) are the deterministic entry
  point. This is the actual answer to "how do I make sure the right things
  happen in the right order": you type `/run-pipeline projects <slug>` and
  the command's own instructions walk every stage explicitly, in the order
  below, rather than hoping the model remembers `CLAUDE.md` unprompted.

**In practice: use the commands.** `/new-project`, `/new-concept`,
`/run-pipeline`, `/test-project`, `/status-project` (see each command file
in `.claude/commands/`) are the intended way to drive this workflow. The
skill/subagent table below is what those commands invoke internally, and
is also there for when you want to run one stage manually instead of the
full pipeline (e.g. "just re-run `/test-project` after I hand-edited a
file").

## Full sequence

| # | Step | Skill | Subagent (if isolating context) | Gate / output |
|---|---|---|---|---|
| 1 | Draft the brief | `write-project-brief` / `write-concept-brief` | — | `project_brief.md` / `concept_brief.md`, user-approved |
| 2 | Resolve ambiguity | `clarify-requirements` | `requirements-clarifier` | No open questions remain; decisions recorded in the brief |
| 3 | **Require API key — hard stop** | `require-api-key` | — | Real provider key present AND verified with an actual call. **No mock mode exists — nothing past this point runs without it.** |
| 4 | Architecture | `technical-design` | `planner` | `design.md`, user-reviewed |
| 5 | Test cases | `write-and-validate-tests` | `planner` | Plain-language test list, **user confirms it matches intent** |
| 6 | Task breakdown | `make-plan` | `planner` | `plan.md`, ends with integrate-and-assemble + run-and-verify |
| 7 | Env + deps | `setup-venv`, `pick-requirements` | `backend-builder` | venv created, `requirements.txt`/`package.json` pinned |
| 8 | Shared plumbing | `helper-utils` (copies from `_shared/`) | `backend-builder` | `config.py`, `llm_client.py` in place, real provider wired, no mock fallback |
| 9 | Backend | `backend-fastapi` | `backend-builder` | API contract from `design.md` implemented |
| 10 | Agent/graph | `agent-langgraph` (default) / `agent-crewai` / `agent-dspy` / `agent-mcp-real` / `agent-graphrag` — pick the one `design.md` names | `agent-builder` | Agent module with one clean entrypoint; **research-first + spike-first required for every option except agent-langgraph** |
| 11 | Frontend | `frontend-nextjs` (default) or `frontend-streamlit` / `notebook-concept` | `frontend-builder` | UI calling only documented endpoints |
| 12 | Implement tests per-slice | (continuation of `write-and-validate-tests`) | whichever builder owns the code under test | Each builder's own new tests green before moving to the next slice |
| 13 | **Full test gate** | `run-tests` | `integrator` | **This is the step that certifies "tests passed."** Real captured pass/fail output, full suite, 100% green or documented skips |
| 14 | Security | `security-check` — only if tool-calling/DB/untrusted-content in scope | `integrator` | Blocked-attempt test recorded (e.g. rejected destructive SQL) |
| 15 | Eval/observability | `eval-and-observability` — only if RAG/quality claims in scope | `integrator` | Tracing wired, eval numbers recorded |
| 16 | Static checks | `lint-and-typecheck` | `integrator` | Type check + lint clean |
| 17 | Env audit | `validate-env` | `integrator` | `.env.example` matches code; missing required var fails loudly (no fallback) |
| 18 | Integration | `integrate-and-assemble` | `integrator` | Single run command; contracts/env/deps reconciled |
| 19 | End-to-end proof | `run-and-verify` | `integrator` | One real request driven through the live, freshly-installed app, against the real provider |
| 20 | Final review | — (code-review + brief-fidelity pass) | `reviewer` | Confirms output matches brief; flags scope drift |
| 21 | Deploy config | `deploy-config` — only if brief requires it | — | `vercel.json` / `render.yaml` / `Dockerfile` |

## Why this order

- **Clarify before design, always.** Guessing at requirements is the single
  most expensive mistake to make late — it compounds through design, tests,
  and code.
- **No mock mode, ever — the API key gate runs before design, not before
  run.** This repo intentionally does not have a mock/offline path. If
  design and code got written before a key was confirmed, you'd only find
  out the project can't actually run at the very end. `require-api-key`
  moves that discovery to the earliest possible point and makes it a hard
  stop, not a warning.
- **Tests before build (step 4-5), with a human checkpoint.** Writing test
  cases from the same reading of the brief that produces the code risks
  encoding one misunderstanding twice. The explicit "does this list match
  your intent?" question in `write-and-validate-tests` is the check for
  that — it's asked before any test or implementation code exists, not
  during final review.
- **Agent framework choice is never silent.** Step 9 always picks the
  skill matching what `design.md` names. Substituting `agent-langgraph`
  for a brief that names CrewAI or DSPy is exactly the "substitution not
  allowed" failure this repo's rules forbid elsewhere (see root
  `CODEX.md`).
- **Research-first and spike-first apply only where they earn their cost.**
  LangGraph/FastAPI/Next.js are stable and well-represented in the model's
  training data — skip the extra step there. CrewAI, DSPy, real MCP, and
  GraphRAG are narrower and faster-moving, so those skills mandate a docs
  check and a standalone spike before the API is trusted.
- **Security and eval run after code exists but before integration.**
  Checking a fully-formed backend/agent is more useful than checking
  partial code, but catching a rejected-SQL-injection gap here is cheaper
  than catching it in `run-and-verify` or, worse, not catching it at all.
- **Static checks (lint/typecheck) run before integration, not instead of
  `run-and-verify`.** They catch a different class of bug (type errors in
  paths the smoke test doesn't exercise) — neither step substitutes for
  the other.
- **`validate-env` runs before `integrate-and-assemble`** so integration
  isn't reconciling env vars that are already wrong; then
  `integrate-and-assemble` still does its own env-name cross-check as part
  of stitching frontend/backend together.
- **`integrate-and-assemble` and `run-and-verify` are always last, always
  both.** A project isn't done because its parts exist — it's done when one
  real request actually completes end to end, freshly installed.
- **`reviewer` runs only after a passing verify**, so it's reviewing
  working code against intent, not reviewing code that doesn't even run
  yet.

## Three tracks, not one

This repo has three separate pipelines with different weight, for
different purposes — don't run the heavy one where the light one fits:

| Track | Folder | Purpose | Pipeline | Command |
|---|---|---|---|---|
| Projects | `projects/` | Shippable end-to-end app | Full 21-stage (below) | `/run-pipeline projects <slug>` |
| Concepts | `concepts/` | Certification-grade atomic notebook (7-part contract, user-confirmed tests) | Full 21-stage (below) | `/run-pipeline concepts <slug>` |
| Teaching | `teaching/` | Live classroom demo, progressive multi-step (e.g. "API call → system prompt → tool call → memory → basic RAG"), meant to grow across a whole day | `teaching-brief` → `teaching-build` → `teaching-verify` (initial); `teaching-add-step` → `teaching-build` (append) → `teaching-verify` (each later addition); `teaching-debug` auto-invoked on any failure | `/new-teaching-demo`, `/run-teaching-pipeline`, then `/add-teaching-step` repeatedly |

The teaching track deliberately skips the formal `clarify-requirements`,
`write-and-validate-tests`, `security-check`, `eval-and-observability`,
`lint-and-typecheck`, `validate-env`, `integrate-and-assemble`, and
`deploy-config` steps — those exist to make something shippable/
certifiable, and a live demo doesn't need that ceremony. If a specific
teaching demo does need one of those (e.g. a security-check because a step
queries a real database), ask for it explicitly rather than running the
full pipeline for the whole demo.

It keeps three things instead, in place of that ceremony:
- **`require-api-key`, still a hard stop.** No mock mode in this track
  either — a real, verified provider key is mandatory before
  `teaching-build` ever runs, same rule as the full pipeline.
- **Paraphrase-and-confirm** before touching any file — both for the
  initial brief (`teaching-brief`) and every later addition
  (`teaching-add-step`). This is the track's one mandatory requirements
  checkpoint.
- **Automatic iterative debugging** on any failure (`teaching-debug`,
  invoked by `teaching-verify`) — it doesn't stop at the first error, it
  keeps trying genuinely different fixes until the artifact runs, or
  reports exactly what's blocking it if it's genuinely stuck. A dead API
  key is treated as a hard stop here too, not something to debug around.

## Commands (`.claude/commands/`)

| Command | Does |
|---|---|
| `/new-project <slug>` | Drafts `project_brief.md` via `write-project-brief`, stops for review — no code. |
| `/new-concept <slug>` | Drafts `concept_brief.md` via `write-concept-brief`, stops for review. |
| `/run-pipeline <projects\|concepts> <slug>` | Runs the entire sequence below end to end. Hard-stops if no working API key is configured, and at the clarify and test-confirmation checkpoints, and on any failing gate. |
| `/test-project <projects\|concepts> <slug>` | Runs `run-tests` standalone — re-certifies the test gate any time, independent of a full pipeline run. |
| `/status-project <projects\|concepts> <slug>` | Reports which stages are actually done, re-checking the filesystem/tests rather than trusting `plan.md`'s checkboxes. |
| `/new-teaching-demo <slug>` | Drafts `teaching_brief.md` (ordered steps, notebook/script format) — the lightweight track. |
| `/run-teaching-pipeline <slug>` | Hard-stops if no working API key first (`require-api-key`), then builds the progressive notebook/script + verifies it against the real provider; auto-debugs on failure. |
| `/add-teaching-step <slug>` | Extends an EXISTING teaching demo — clarifies + paraphrases the new step, appends without disturbing earlier steps, re-verifies the whole artifact. Run this as many times as needed across a day. |

## Quick lookup by question

- *"I have an idea but no brief yet."* → `write-project-brief` /
  `write-concept-brief`.
- *"Can I build/test this without an API key, in mock mode?"* → No. This
  repo has no mock mode, in any track. `require-api-key` is a hard stop —
  set a real `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GROQ_API_KEY` in `.env`
  first.
- *"The brief is vague on X."* → `clarify-requirements` — ask, don't guess.
- *"Which agent framework skill do I use?"* → whatever `design.md` names.
  Default is `agent-langgraph`. Never substitute for a named framework.
- *"Do I need `security-check`?"* → yes if the project calls tools, touches
  a database, or ingests content the user didn't type directly.
- *"Do I need `eval-and-observability`?"* → yes if it's RAG or the brief
  makes a quality/reliability claim.
- *"My tests keep failing after a fix."* → keep fixing and re-running
  before moving to the next `plan.md` step — a failing test blocks
  progress, it isn't deferred.
- *"After the app is built, how do I know the tests actually passed?"* →
  `run-tests`, owned by `integrator`, step 12. It's the one full-suite run
  with captured real output that counts — per-slice runs during build
  (step 11) don't certify the whole project on their own, since later
  fixes can break earlier work.
- *"How do I know it's actually done?"* → `run-and-verify` passes, freshly
  installed, with a real request driven through it, and `reviewer` has
  confirmed it matches `project_brief.md`.
