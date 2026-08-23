---
description: Run the full brief-to-verified-app pipeline for a project or concept, stage by stage, per WORKFLOW.md. For projects/, includes a mandatory architecture-design stage (single/multi-agent, RAG/Agentic RAG, MCP tools) before design.md is written. Hard-stops if no working API key is configured, at the clarify and test-case-confirmation checkpoints, and on any failing gate.
argument-hint: <projects|concepts> <slug>
---

Parse `$ARGUMENTS` as `<kind> <slug>` (kind is `projects` or `concepts`).
`$1/$2/` is the working folder for this run (e.g. `projects/01_basic_chatbot/`).

This command drives the entire `WORKFLOW.md` sequence for one unit. Follow
it exactly, in order, and do not skip or reorder steps. Use `TaskCreate`/
`TaskUpdate` to track each stage so progress is visible.

**For `projects/`, architecture design (Stage 1b below) is mandatory, not
optional** — every project built through this command gets a real
single-vs-multi agent decision, a real design-pattern decision (including
whether the usecase is plain RAG, Agentic RAG, or no retrieval at all),
and a real tool-sourcing pass (MCP-server-first) before `design.md` is
written. This is the same architecture-design stage
`/agent_system_design_to_build_onego` runs for teaching demos, applied
here to `projects/`. **`concepts/` skips Stage 1b** — concepts are
notebook-scale, atomic, single-thing demos by definition (see `CLAUDE.md`),
and don't warrant a full topology/memory/loop-engineering design pass; a
concept still gets `technical-design`'s own lightweight Agentic-RAG/MCP
detection (its steps 0a/0a2) instead.

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
1b. **Architecture design — mandatory for `projects/`, skipped for
    `concepts/`.** Check whether `$1/$2/architecture_design.md` or
    `$1/$2/system_design/architecture_design.md` already exists and is
    approved. If so, reuse it — go straight to stage 2. If not (and
    `kind` is `projects`):
    a. Ask the user to choose the design process, same as
       `/agent_system_design_to_build_onego` Step 3: **staged**
       (`agent-system-design`, the full 8-stage gated pipeline —
       recommended when tools/memory/loop design are non-trivial or the
       user wants to see the reasoning at each decision point) or
       **one-shot** (`agent-architecture-design`, a single interview
       producing one `architecture_design.md` directly — recommended for
       a small, clearly-bounded usecase). Feed `project_brief.md` and
       stage 1's clarified answers in as pre-answered context so neither
       process re-asks them.
    b. Run the chosen process to completion, with real explicit approval
       at every stage/step — this is where single-vs-multi-agent, the
       design pattern (deterministic code / fixed workflow / RAG
       assistant / Agentic RAG / bounded ReAct / planner-executor /
       supervisor / human-governed), and tool sourcing (MCP-server-first,
       preferred by default whenever one exists) actually get decided.
       Never skip or infer a stage's answer.
    Point the output at `$1/$2/` (`system_design/` for staged, or
    `architecture_design.md` directly for one-shot) — same layout
    `/agent_system_design_to_build_onego` uses for `teaching/<slug>/`.
2. **Design** — `technical-design` (or spawn `planner`). If stage 1b
   produced (or found) an approved architecture design, `technical-design`
   maps its decisions directly into `design.md` — chosen pattern into
   Agent/graph (including which `agent-agentic-rag` capabilities are in
   scope, if Agentic RAG), the tool inventory's sourcing decisions
   (MCP-server name or otherwise) into Components/Tech choices — instead
   of re-deriving them, and its own steps 0a/0a2 (Agentic RAG / MCP
   detection) are skipped since stage 1b already answered those. (For
   `concepts/`, where stage 1b doesn't run, steps 0a/0a2 still apply
   directly.) For `projects/`, it then **explicitly asks the user**
   whether they want a Jupyter notebook prototype or a full frontend +
   FastAPI backend production-style app — do not assume either. Produce
   `design.md`. Briefly show it to the user; proceed unless they object
   (this is not a hard stop, just a courtesy pause — say what you're about
   to do and give a moment to redirect).
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
   b1. `synthetic-data-generator` — if `design.md` describes a concrete
      input data shape (CSV/PDF/transcript/etc.) with no real sample data
      supplied, generate it into `data/` now, before the steps below that
      consume it. Skip only if real sample data already exists or the
      input is pure runtime free-text with nothing to seed.
   c. `backend-fastapi` (if applicable)
   d. the agent skill matching what `design.md` names
      (`agent-langgraph`/`agent-crewai`/`agent-dspy`/`agent-mcp-real`/
      `agent-graphrag`/`agent-agentic-rag`) — apply `research-first` +
      spike-first for everything except `agent-langgraph`/`agent-agentic-rag`
      (the latter is a LangGraph topology, not a separate framework, so it
      shares LangGraph's well-covered-in-training-data exemption)
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
