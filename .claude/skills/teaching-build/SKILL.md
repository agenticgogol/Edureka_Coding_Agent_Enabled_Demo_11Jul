---
name: teaching-build
description: Use after teaching_brief.md is approved. Builds the progressive notebook/script one step at a time, each step visibly adding to the previous, runnable and shown before moving to the next. For full_app format, evaluates build complexity, recommends inline vs delegated (backend-builder/frontend-builder/integrator) execution, and asks the user to choose before generating any code.
---

# Teaching Build

Builds `teaching/<slug>/teaching_brief.md`'s ordered steps as one
progressively-growing artifact — not separate isolated files per step.
The point is that a student watching sees step (b)'s code as step (a)'s
code plus one clear addition, not a fresh unrelated example.

## When to use

- **Initial build**: after `teaching_brief.md` is approved, in place of the
  full `write-and-validate-tests` → `make-plan` → component-skill chain
  used for `projects/`/`concepts/`. This skill alone does the building.
- **Append mode**: called by `teaching-add-step` after it has paraphrased
  and confirmed a new step with the user. In this mode, only build the new
  step(s) — do not regenerate or rewrite cells/code for steps that already
  exist and were already verified, unless the new step genuinely requires
  changing something upstream (and if so, flag that explicitly before
  doing it).

## Procedure

0. Read `teaching_brief.md`'s `## Format` field first. `notebook` follows
   steps 1-6 below unchanged. `full_app` (Streamlit + FastAPI) instead
   follows the **Full-app build** section further down — do not build a
   notebook when the brief says `full_app`, and vice versa.

1. For **notebook** format: create `teaching/<slug>/notebook.ipynb`. For
   each step in order:
   - One markdown cell: what this step adds and why, 2-4 sentences.
   - One code cell: the previous step's code plus this step's addition,
     clearly delineated (a short comment marking what's new is fine, but
     don't over-comment). Each cell must be runnable on its own once
     prior cells have executed — a student stepping through top-to-bottom
     always has working code at every point, not just at the end.
   - One short cell or printed output showing the step actually working
     (e.g. print the response, print the tool call trace, print retrieved
     chunks).
   - Skip formal "Exercise"/"Challenge task" sections unless the user asks
     for them — this is a demo sequence, not the certification-grade
     notebook contract from `notebook-concept`.
2. For **script/small project** format: create `teaching/<slug>/app.py`
   (or `teaching/<slug>/steps/step_a_*.py`, `step_b_*.py`, ... if the user
   wants each step individually runnable and diffable) — same principle,
   each step's file is the previous plus one addition.
3. Route any LLM calls through a minimal inline provider-swap (reuse
   `_shared/llm_client.py`/`config.py` via `helper-utils` if the sequence
   is non-trivial enough to warrant it — for a 5-step demo like "API call
   → system prompt → tool call → memory → basic RAG," it's worth it since
   step (a)'s client setup is reused by every later step).
   If `teaching_brief.md`'s `## MCP tools` names a server (not `none`), the
   tool-calling step should build that call via `agent-mcp-real` Mode B
   (connect as a client to the named public server) rather than a
   hand-written function — show the client actually spawning/connecting to
   the real server process and getting a real tool result, since that's
   the whole point of the demo step.
4. No mock mode — every step calls a real provider. `require-api-key` must
   have already verified a working key before `teaching-build` runs (this
   is checked once per demo, not per step); build cells assuming that key
   is live, and let a genuine failure surface as a real error for
   `teaching-debug` to handle, not a silent mock fallback.
5. For the RAG-type step specifically (or any step needing sample data):
   this should normally already be handled — `run-teaching-pipeline` and
   `agent_system_design_to_build_onego` both run `synthetic-data-generator`
   before calling `teaching-build`. If this skill is invoked standalone and
   `teaching/<slug>/data/` doesn't yet have what a step needs, run
   `synthetic-data-generator` now rather than improvising sample files
   inline — don't require the user to supply a real PDF before the demo
   runs once. If `teaching_brief.md`'s `RAG mode` is `agentic`, build that step per
   `agent-agentic-rag` (its core decide/retrieve/grade/rewrite loop, plus
   only the optional capabilities the brief's `Agentic RAG capabilities`
   line names) instead of a single fixed retrieve-then-generate call — show
   the loop actually running (e.g. print each retrieval round and its
   grade) so the student sees the agentic behavior, not just a final
   answer. If `RAG mode` is `fixed` or `n/a`, a plain `vector-store` call is
   correct and `agent-agentic-rag` should not be invoked.
6. When done, all steps live in one artifact a student can run top to
   bottom and see the concept build up live.

## Full-app build (when `teaching_brief.md`'s Format is `full_app`)

This is a lighter version of the `projects/` component chain, scoped to
what one classroom demo needs — still real code, real provider calls, no
mock mode, but skipping the ceremony (`lint-and-typecheck`,
`validate-env`, formal `plan.md`) that a shippable project carries.

### Step 0: execution mode — ask, don't assume

Before writing any code, evaluate this build's complexity and ask the user
to pick how it should be built. Never silently choose either mode.

1. **Evaluate complexity** from what's actually in scope for *this* build
   call (not the demo's eventual full ambition — just what's being
   generated right now):
   - Number of steps/features in scope (initial build: how many brief
     steps; append mode: usually 1, but check how many prior
     `/add-teaching-step` rounds already exist on this artifact).
   - Whether a vector store is wired (`## Vector store` != `none`).
   - Whether observability is wired (`## Observability` == `phoenix`).
   - Rough existing code size if this is an append onto a demo that's
     already grown (check line counts of `backend/`/`frontend/`).
   - Treat as **low complexity** (recommend inline): initial build with
     1-2 steps, no vector store, no observability, or any append call onto
     a demo with fewer than ~3 prior additions.
   - Treat as **higher complexity** (recommend delegated): initial build
     with 3+ steps, or a vector store + observability both wired, or an
     append onto a demo that already has 3+ prior additions — the main
     conversation's context is carrying enough (gated Q&A history, prior
     builds, prior debug sessions) that isolating frontend/backend into
     separate subagents is worth the extra coordination cost.
2. **Ask the user**, stating your recommendation and the reasoning in one
   short message: "This build is `<low/higher>` complexity because
   `<the specific factors from step 1>`. I recommend `<inline / delegated>`.
   Do you want me to (a) build it myself in one pass, or (b) delegate to
   `backend-builder`/`frontend-builder` subagents with `integrator`
   reconciling them?" Wait for the user's choice — do not proceed on the
   recommendation alone without confirmation.
3. Branch on the answer:
   - **Inline**: follow steps 1-7 below directly, in this conversation.
   - **Delegated**: spawn `backend-builder` and `frontend-builder` (via
     the `Agent` tool) as separate agents, each scoped to steps 1-3 and
     step 4 respectively below (backend gets `helper-utils` +
     `vector-store` + `backend-fastapi`; frontend gets
     `frontend-streamlit`) — brief each with `teaching_brief.md`'s
     content standing in for `design.md` (there's no separate design doc
     in this track, so pass the brief's Format/Vector store/Observability/
     happy-path fields as the contract). Then spawn `integrator` (or do it
     inline if the reconciliation is trivial) to run step 5-7 below:
     wire observability if applicable, verify the frontend's calls match
     the backend's actual routes, and record the run command. Subagent
     summaries describe intent, not guaranteed fact — after they report
     back, do the same manual contract check step 6 calls for before
     trusting the result.

### Steps (inline mode, or per-slice in delegated mode)

1. `helper-utils` — copy `_shared/config.py` / `_shared/llm_client.py`
   into `teaching/<slug>/backend/`, wired to the provider(s) the brief
   names.
2. If `teaching_brief.md`'s `## Vector store` is not `none`: run
   `vector-store` to scaffold ingestion/query for the named store
   (ChromaDB / FAISS / Qdrant Cloud) before wiring the backend endpoints
   that use it. If `## RAG mode` is `agentic`, also run `agent-agentic-rag`
   to build the LangGraph retrieval loop on top of that store — wiring only
   the capabilities `## Agentic RAG capabilities` names — and have the
   backend endpoint call into that graph instead of a single fixed
   retrieve-then-generate call.
2a. If `teaching_brief.md`'s `## MCP tools` names a server (not `none`/
   `declined`): run `agent-mcp-real` Mode B to build the client connecting
   to that named public server, and confirm any credentials the underlying
   service needs (per that server's own docs) are in `.env` and covered by
   `require-api-key`-style verification before the backend endpoint that
   calls it is considered done.
3. `backend-fastapi` — one endpoint per step in the brief's step list
   (e.g. step (a)'s endpoint, step (b) extends it, etc.), matching however
   many of the brief's steps are in scope for this build. Keep the same
   "each step builds on the previous" spirit as the notebook mode, just
   expressed as incrementally-added routes/logic instead of cells.
4. `frontend-streamlit` — one `app.py` UI that exercises the happy-path
   test case approved in `teaching-brief` step 4 end to end (e.g. provider/
   model picker if that's in scope, chat input, response display).
5. If `teaching_brief.md`'s `## Observability` is `phoenix`: run
   `eval-and-observability`'s tracing portion (Phoenix if
   `PHOENIX_COLLECTOR_ENDPOINT` is set, else local OSS Phoenix, else
   structured JSON span logs as the last-resort fallback) — skip its
   formal eval-set/Ragas portion unless the user separately asks for
   measured quality claims; a teaching demo needs traces to show
   observability working, not necessarily a scored eval suite.
6. No `integrate-and-assemble`/`lint-and-typecheck`/`validate-env` — this
   is the teaching track's deliberate lighter weight. Do make sure the
   frontend's calls match the backend's actual routes (a quick manual
   contract check is enough, not the formal integration skill).
7. Record the single run command (e.g. `uvicorn backend.main:app --reload`
   in one terminal, `streamlit run app.py` in another, or a combined
   `./run.sh` if you write one) in `teaching/<slug>/README.md`.
