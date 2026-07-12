---
description: Run the full brief-to-verified-app pipeline for a project or concept, stage by stage, per WORKFLOW.md. Hard-stops if no working API key is configured, at the clarify and test-case-confirmation checkpoints, and on any failing gate.
argument-hint: <projects|concepts> <slug>
---

Parse `$ARGUMENTS` as `<kind> <slug>` (kind is `projects` or `concepts`).
`$1/$2/` is the working folder for this run (e.g. `projects/01_basic_chatbot/`).

This command drives the entire `WORKFLOW.md` sequence for one unit. Follow
it exactly, in order, and do not skip or reorder steps. Use `TaskCreate`/
`TaskUpdate` to track each stage so progress is visible.

## Preconditions

- `$1/$2/project_brief.md` (or `concept_brief.md`) must exist. If not,
  stop and tell the user to run `/new-project $2` or `/new-concept $2`
  first.

## Stages (run in order; each stage's skill/subagent is named in WORKFLOW.md)

1. **Clarify** — `clarify-requirements` (or spawn `requirements-clarifier`).
   **STOP AND WAIT** for the user's answers if any open question exists.
   Do not proceed on assumptions.
1a. **Require API key** — `require-api-key`. **HARD STOP** if no provider
    key is set or the configured key fails a real verification call. There
    is no mock mode in this repo — nothing past this point runs without a
    working key. Do not draft `design.md` or write any code until this
    passes.
2. **Design** — `technical-design` (or spawn `planner`). For `projects/`,
   this starts by **explicitly asking the user** whether they want a
   Jupyter notebook prototype or a full frontend + FastAPI backend
   production-style app — do not assume either. Produce `design.md`.
   Briefly show it to the user; proceed unless they object (this is not a
   hard stop, just a courtesy pause — say what you're about to do and give
   a moment to redirect).
3. **Draft and confirm tests** — `write-and-validate-tests`. Draft the
   plain-language test list. **STOP AND WAIT** for explicit user
   confirmation that the list matches their intent. This is a hard
   checkpoint, same as clarify — do not treat silence or a vague reply as
   confirmation.
4. **Plan** — `make-plan`. Produce `plan.md` from the template (includes
   `run-tests`, and conditionally `security-check`/`eval-and-observability`
   based on what step 2's design actually needs).
5. **Build**, in order, each committing its own tests as it goes:
   a. `setup-venv`, `pick-requirements`
   b. `helper-utils` (copy from `_shared/`)
   c. `backend-fastapi` (if applicable)
   d. the agent skill matching what `design.md` names
      (`agent-langgraph`/`agent-crewai`/`agent-dspy`/`agent-mcp-real`/
      `agent-graphrag`) — apply `research-first` + spike-first for
      everything except `agent-langgraph`
   e. `frontend-nextjs` / `frontend-streamlit` / `notebook-concept`
6. **Full test gate** — `run-tests`. Real captured pass/fail output. If
   failures exist, invoke `project-debug` to reproduce/diagnose/fix and
   re-run; **do not proceed past this stage on a failing suite.**
7. **Security** — `security-check`, only if `design.md` involves tool
   calling, DB access, or untrusted-content ingestion.
8. **Eval/observability** — `eval-and-observability`, only if `design.md`
   involves RAG or makes a quality/reliability claim.
9. **Static checks** — `lint-and-typecheck`. Fix all reported issues.
10. **Env audit** — `validate-env`. Confirm a missing required key fails
    loudly and immediately — actually test this by unsetting it, don't
    assume it. No mock/degraded fallback should ever run instead.
11. **Integrate** — `integrate-and-assemble`. Produces the single run
    command.
12. **Verify** — `run-and-verify`. Install fresh, launch via the single run
    command, drive one real end-to-end request. **If this fails, invoke
    `project-debug` to fix and re-run — the pipeline is not done until
    this passes.**
13. **Review** — spawn `reviewer` (or do it inline): confirm the result
    matches `project_brief.md`'s Definition of Done, flag scope drift.
14. **Deploy config** — `deploy-config`, only if the brief explicitly
    requires deployment.

## After the pipeline completes

If the user reports a bug later (after `run-and-verify` already passed
once), use `/fix-bug <kind> <slug> <description>` rather than re-running
this whole pipeline — it reproduces the report, fixes it via
`project-debug`, and re-certifies `run-tests` + `run-and-verify` only.

## On failure at any stage

Stop, report exactly what failed and why (real error output, not a
summary), fix it, and re-run that stage (and any stage whose output it
invalidates — e.g. a fix during integration means re-running `run-tests`
and `run-and-verify`, not just continuing forward). Never mark a stage
complete and move on while it's actually failing.

## On completion

Run `python scripts/validate_coding_agent_demo.py` and report the final
state: what was built, the one command to run it, and the confirmed
end-to-end result from stage 12.
