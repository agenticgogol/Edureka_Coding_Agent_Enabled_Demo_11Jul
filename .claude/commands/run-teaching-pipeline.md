---
description: Build a progressive teaching demo end to end — description, mandatory architecture design (single/multi-agent, RAG/Agentic RAG, MCP tools), gated clarification/format/observability/vector-store checkpoints, build, auto-debugged verify. Lighter than /run-pipeline but with real user-approval gates at every decision point.
argument-hint: <teaching-slug>
---

`$ARGUMENTS` is the teaching demo slug under `teaching/`.

This is intentionally lighter than the 21-stage `/run-pipeline` — no
`write-and-validate-tests` full test-list authoring, no
`security-check`/`lint-and-typecheck`/`validate-env`/
`integrate-and-assemble`/`deploy-config` — those exist for shippable
projects and certification-grade concepts, not a live classroom demo. But
it is **not** a silent one-shot build either: every decision the old
shortcut version used to assume gets a real, explicit checkpoint below. Do
not skip, reorder, or batch-approve these — each is its own stop.

**Architecture design (Stage 1.5 below) is mandatory, not optional** —
every teaching demo built through this command gets a real single-vs-multi
agent decision, a real design-pattern decision (including whether the
usecase is plain RAG, Agentic RAG, or no retrieval at all), and a real
tool-sourcing pass (MCP-server-first) before any brief question gets
asked. This command runs the same architecture-design stage
`/agent_system_design_to_build_onego` runs — the two commands differ only
in whether you also want that command's fixed upfront clarifying
checklist; this one gathers the same information through `teaching-brief`'s
own checkpoints instead. If you already have an approved
`architecture_design.md` or `system_design/` for this slug (e.g. from a
prior `/agent-system-design` or `/agent_system_design_to_build_onego` run),
this command reuses it rather than re-running the design stage.

## Preconditions

- `teaching/$ARGUMENTS/` must exist (from `/new-teaching-demo $ARGUMENTS`).
  If not, stop and tell the user to run that first.
- Treat the folder as resumable state, regardless of whether Claude Code
  or Codex created the earlier files. Before asking anything, inspect
  `teaching_brief.md`, generated artifacts, and `README.md`, then continue
  from the first incomplete checkpoint. Do not regenerate completed work
  silently.

## Stages

1. **Get the description.** If `teaching_brief.md` doesn't exist yet, ask
   the user directly: "What do you want to build?" — open-ended, no format
   expected. If a `teaching_brief.md` already exists with an approved
   description, skip to the first not-yet-approved checkpoint below
   instead of re-asking (check the brief for which sections are already
   filled in and confirmed).
   If code artifacts already exist and `README.md` records a successful
   verify, report that the initial pipeline appears complete and suggest
   `/add-teaching-step $ARGUMENTS` for extension or
   `/fix-bug teaching $ARGUMENTS <description>` for a reported issue.
1.5. **Architecture design — mandatory.** Before any brief question gets
   asked, check whether `teaching/$ARGUMENTS/architecture_design.md` or
   `teaching/$ARGUMENTS/system_design/architecture_design.md` already
   exists and is approved. If so, reuse it — skip straight to 1.5c. If not:
   a. Ask the user to choose the design process, same as
      `/agent_system_design_to_build_onego` Step 3: **staged**
      (`agent-system-design`, the full 8-stage gated pipeline — recommended
      when tools/memory/loop design are non-trivial or the user wants to
      see the reasoning at each decision point) or **one-shot**
      (`agent-architecture-design`, a single interview producing one
      `architecture_design.md` directly — recommended for a small,
      clearly-bounded usecase). Feed stage 1's description in as
      pre-answered context so neither process re-asks it.
   b. Run the chosen process to completion, with real explicit approval at
      every stage/step — this is where single-vs-multi-agent, the design
      pattern (deterministic code / fixed workflow / RAG assistant /
      Agentic RAG / bounded ReAct / planner-executor / supervisor /
      human-governed), and tool sourcing (MCP-server-first, preferred by
      default whenever one exists) actually get decided. Never skip or
      infer a stage's answer.
   c. Run `teaching-brief-from-system-design` against the approved design
      to produce an initial `teaching_brief.md` draft — this pre-fills
      `Description`, `Observability`, `Vector store`, `RAG mode`/`Agentic
      RAG capabilities`, `MCP tools`, `Constraints`, and `Audience level`
      from the design's actual decisions, marking every checkpoint
      `pending`, not approved.
2. **Clarify and gate through `teaching-brief`.** Hand the description
   (and, if 1.5 ran, the pre-filled draft) to
   the `teaching-brief` skill and follow its full checkpoint sequence, in
   order, stopping for real user approval at each:
   a. Clarifying questions for genuine gaps only (batched, with concrete
      options).
   b. Format — notebook/script vs full Streamlit+FastAPI app — asked only
      if not already stated.
   c. The one happy-path test case, from the user's flow, shown for
      approval.
   d. Confirmation that `.env` has the required key(s), followed by a real
      `require-api-key` verification call. **HARD STOP** if it fails —
      report the exact error, do not proceed until a real key verifies.
      No mock mode exists in this repo.
   e. Observability — Phoenix or none — asked only if not already stated.
   f. Vector store — ChromaDB / FAISS / Qdrant Cloud / none — asked only
      if not already stated. If Qdrant Cloud, fold its credential check
      into step 2d if that already happened, or re-run `require-api-key`-
      style verification for `QDRANT_URL`/`QDRANT_API_KEY` now. If a
      vector store was chosen, also settle RAG mode (fixed vs. agentic,
      and which `agent-agentic-rag` capabilities if agentic) per
      `teaching-brief`'s own step 7 follow-up.
   g. External tools — `teaching-brief`'s step 8: look up whether a free
      public MCP server covers any tool/capability the demo needs and
      **recommend it by default** over custom tool code; record the
      choice (or `none` if the demo needs no tools). If a server is
      chosen, its underlying service's credential goes through the same
      `require-api-key`-style verification as step 2d/2f.
   h. Final "ready to generate the code?" confirmation, after summarizing
      everything decided above (`teaching-brief`'s step 9).
   Do not call `teaching-build` until 2h's explicit yes. **Never treat a
   value 1.5c pre-filled as approved** — pre-filling is a draft, not
   consent; every checkpoint above still needs a real explicit approval in
   the conversation, per `teaching-brief-from-system-design`'s own ground
   rules.
3. **Build** — first `synthetic-data-generator`, if `teaching_brief.md`
   describes a concrete input data shape (CSV/PDF/transcript/etc.) with no
   real sample data supplied — generate it into `teaching/$ARGUMENTS/data/`
   before `teaching-build` runs. Skip only if real sample data already
   exists or the input is pure runtime free-text with nothing to seed.
   Then `teaching-build`. Reads `teaching_brief.md`'s `Format`
   field and builds accordingly: the progressive notebook/script (each
   step visibly building on the last), or the full Streamlit+FastAPI app
   (wiring in `vector-store` and/or `eval-and-observability`'s tracing
   portion per what was approved in stage 2), always against the real
   verified provider.
4. **Verify** — `teaching-verify`. For notebook format, run every step top
   to bottom against the real provider. For full_app format, install
   fresh, launch, and drive the approved happy-path test case through the
   real running app. **On any failure, this stage automatically invokes
   the matching debug skill** (`teaching-debug` for notebook/script,
   `project-debug` for full_app) — it iterates on the real error until
   fixed, it does not stop at the first failure and report it. If the
   failure is a key/credential itself, that's a hard stop: report it and
   re-run `require-api-key`, don't work around it.
5. **Report** — summarize what was built, the exact run command(s), which
   provider/model (and vector store / observability setup, if any) it was
   verified against, and tell the user how to run it themselves right now.

## After the user runs it

If the user finds something broken after this pipeline already reported
success, use `/fix-bug teaching $ARGUMENTS <description>` — it reproduces
the report and fixes it via the matching debug skill, without re-running
this whole pipeline.

## Continuing later

This demo is meant to grow across the day. Once built, use
`/add-teaching-step $ARGUMENTS` any number of times to add more steps —
each call clarifies and paraphrases the new addition back to you before
touching any file, appends it without disturbing earlier verified steps,
and re-verifies the whole artifact. Don't re-run `/run-teaching-pipeline`
for incremental additions to an existing demo — that's what
`/add-teaching-step` is for.

## Resume rules

When resuming a partially completed run:

- If neither `architecture_design.md`/`system_design/architecture_design.md`
  nor `teaching_brief.md` exists yet, start at stage 1.5 — architecture
  design is mandatory and comes before any brief work, even on resume.
- If an approved architecture design already exists but `teaching_brief.md`
  doesn't (or exists only as an unapproved 1.5c draft), start at stage 2
  with `teaching-brief`, not stage 1.5 again — don't re-run architecture
  design once it's approved.
- Prefer explicit `## Checkpoint status` entries in `teaching_brief.md`.
  If they are absent, infer conservatively from filled sections and the
  conversation, then add the status section when you next edit the brief.
- Never ask again for decisions already recorded in the brief unless they
  conflict or are ambiguous. Restate them briefly and move to the next
  missing gate.
- If the brief is approved but no artifact exists, start at `teaching-build`.
- If an artifact exists but verify is not recorded in `README.md`, start at
  `teaching-verify`.
- If verify fails during resume, invoke `teaching-debug` or `project-debug`
  exactly as in the normal verify stage.

## On failure

`teaching-debug` handles this automatically as part of `teaching-verify` —
it keeps iterating on genuinely different hypotheses until the artifact
runs, or reports exactly what it tried and what's needed to unblock it if
it's genuinely stuck (e.g. a missing decision only the user can make).
