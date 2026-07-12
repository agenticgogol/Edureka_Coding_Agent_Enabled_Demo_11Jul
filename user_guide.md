# User Guide — Coding_Agent_Enabled_Demo

A practical, task-oriented tutorial. If you want the full mechanics (which
skill/subagent does what, why the ordering is what it is), see
`WORKFLOW.md` — this guide is "what do I actually type."

**Before anything else:** put a real LLM provider key in `.env`
(`cp .env.example .env`, fill in `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or
`GROQ_API_KEY`). There is no mock mode anywhere in this repo — every
pipeline below starts by verifying that key with a real API call, and
refuses to design or write anything until it passes.

---

## 1. I want to build an end-to-end project

Use this when the outcome is a shippable app (frontend + backend, or a
backend-only service) — a chatbot, a RAG assistant, a text-to-SQL tool,
whatever your `project_brief.md` describes.

```
/new-project <slug>
```
Interviews you (problem, definition of done, users, constraints,
non-goals), drafts `projects/<slug>/project_brief.md`, shows it to you,
and stops. Review it before continuing.

```
/run-pipeline projects <slug>
```
Runs the full sequence end to end: clarify → **require a verified API
key** → design → draft-and-confirm tests → plan → build (backend, agent,
frontend) → full test run → security check (if relevant) → eval/
observability (if relevant) → lint/typecheck → env audit → integrate →
end-to-end verify → final review → deploy config (if requested).

It will **stop and wait for you** at exactly two points:
- Clarifying anything ambiguous in the brief.
- Confirming the drafted test cases actually match what you meant, before
  any test or implementation code is written.

Everything else runs automatically, including fixing and re-running any
stage that fails.

**Afterward:**
```
/status-project projects <slug>     # what's actually done, re-checked live
/test-project projects <slug>       # re-run just the test gate after a manual edit
```

**Output:** `projects/<slug>/` containing `project_brief.md`, `design.md`,
`plan.md`, `frontend/`, `backend/`, tests, and a `README.md` with the one
command to run it.

---

## 2. I want a Python notebook or small project explaining a concept

Two tracks fit here, depending on how polished you need it:

### Option A — certification-grade concept notebook (`concepts/`)

Use this for course material that needs to hold up on its own: a full
7-part teaching contract (concept explanation, minimal runnable code,
visual intuition, exercise, expected output, common errors, challenge
task), with a user-confirmed test list.

```
/new-concept <slug>
/run-pipeline concepts <slug>
```
Same full pipeline as projects (minus frontend/backend-specific steps) —
clarify, require API key, design, confirm tests, build via the
`notebook-concept` skill, test, verify.

**Output:** `concepts/<slug>/notebook.ipynb` (or `app.py` for a small demo
app if the brief calls for it) plus brief/design/plan/tests/README.

### Option B — quick, lightweight demo (`teaching/`)

Use this for a fast, live-style walkthrough without the full ceremony —
good for "show me X" without needing certification-grade rigor.

```
/new-teaching-demo <slug>
/run-teaching-pipeline <slug>
```
This is the lightweight gated pipeline: folder creation, open-ended
description, clarifying questions for real gaps, explicit format choice
if needed, one user-flow happy-path testcase for approval, `.env`/API-key
verification, optional Phoenix observability, vector-store choice
(ChromaDB, FAISS, Qdrant Cloud, or none), final ready-to-generate
approval, then build and verify with automatic debugging on any failure.
It skips the full project/concept ceremony: formal test-list authoring,
security/lint/type/env/integration/deploy gates by default.

**Output:** `teaching/<slug>/notebook.ipynb`, a progressive script, or a
Streamlit + FastAPI full-app demo, plus `teaching_brief.md` and
`README.md`.

**Which one to pick:** `concepts/` if this is going into the actual course
and needs the full contract; `teaching/` if you want something fast,
correct, and good enough to demo or iterate on live.

---

## 3. I want to add more features to a notebook/project I already built

This depends on which track it was built in:

### If it's in `teaching/` (the common case for this)

This track is *designed* to grow across a session or a whole day:

```
/add-teaching-step <slug> [<feature description>]
```
Run this as many times as you want. You can pass the feature inline, e.g.
`/add-teaching-step my_rag_demo add CSV upload and Q&A using the same
agent`, or omit it and the agent will ask for the description first. Each
call:
1. Loads the existing notebook/script or full Streamlit+FastAPI app and
   its full step history.
2. Asks enough to pin down the new addition if your request is vague.
3. **Paraphrases the addition back to you in plain language and waits for
   confirmation** before touching any file — e.g. "step (f) will add
   session memory on top of the tool-calling agent from step (c) — right?"
4. Appends the new cells/code for notebook/script demos, or new backend
   route(s) plus Streamlit UI for `full_app`, without disturbing earlier,
   already-verified functionality unless an upstream change is genuinely
   required.
5. Re-runs old and new functionality together (top to bottom for
   notebook/script; original happy path plus the new feature flow for
   `full_app`) and auto-debugs any failure via `teaching-debug` or
   `project-debug` as appropriate.

### If it's in `concepts/` or `projects/`

There's no dedicated "add a feature" command for these tracks yet — they're
meant to be closed out via `/run-pipeline` and then treated as done.
To extend one, just describe the addition directly, e.g.:

> "Add a `/reset` endpoint to `projects/01_basic_chatbot` that clears
> session memory."

Claude will read the existing `design.md`/`plan.md`, clarify if needed,
update the design/plan for the new piece, rebuild only the affected
slice, and re-run `run-tests` + `run-and-verify` before calling it done —
the same discipline as the first build, just scoped to the new piece
instead of the whole project. If you're doing this often for the same
project, it's worth asking Claude to draft a project-local `.claude/skills/`
entry for that recurring kind of change (see §5).

---

## 4. I just want a brief, then straight to code/notebook — minimal ceremony

This is exactly what the **teaching track** is for — it's the shortest
path from an idea to working code in this repo:

```
/new-teaching-demo <slug>
/run-teaching-pipeline <slug>
```

No full-pipeline requirements/design/test-suite/security/lint/env-audit/
integration ceremony. Instead, the teaching pipeline uses the smaller set
of gates that matter for live demos: description, clarifications, format,
one happy-path testcase, verified API keys, observability, vector store,
and ready-to-generate approval. Then it builds and verifies against a real
provider, with automatic debugging if something breaks.

If you want it even faster and are confident in the brief already, you can
hand-write `teaching/<slug>/teaching_brief.md` yourself (copy the shape
from `skills/teaching-brief/SKILL.md`'s template) and skip
straight to `/run-teaching-pipeline <slug>` — it'll still paraphrase back
what it's about to build from your brief before writing anything, but you
skip the interactive interview.

For a shippable project you still want fast, `/run-pipeline` is the
better fit — it just does more (real test suite, security/eval checks,
integration) because that's what "shippable" requires. There's no
shortcut version of the full pipeline; if you don't want that ceremony,
that's the signal to use `teaching/` instead.

---

## 5. Other things this setup can do

- **Check progress without guessing**: `/status-project <projects|concepts>
  <slug>` re-checks the filesystem and re-runs the test gate rather than
  trusting `plan.md`'s checkboxes, which can go stale.
- **Re-certify tests standalone**: `/test-project <projects|concepts>
  <slug>` any time after a manual edit, without running the whole
  pipeline again.
- **Named-framework agents, not just LangGraph**: if a brief specifically
  calls for CrewAI, DSPy, real multi-process MCP, or GraphRAG, the pipeline
  picks the matching `agent-*` skill automatically (never silently
  substitutes LangGraph) and runs `research-first` + a standalone spike
  before wiring it in, since those frameworks move faster than the model's
  training data.
- **Security checks for anything that touches tools/DB/untrusted content**:
  `security-check` runs automatically when relevant (e.g. it'll demand a
  real blocked-SQL-injection test for a text-to-SQL project) — you don't
  have to remember to ask for it.
- **Eval/observability for RAG or quality claims**: `eval-and-observability`
  wires tracing and runs a real eval pass (Ragas or a scripted judge)
  instead of just asserting the thing works.
- **Deployment configs**: if a brief says it needs to deploy, `deploy-config`
  generates `vercel.json`/`render.yaml`/`Dockerfile` — only when asked, not
  by default.
- **Shared plumbing reused everywhere**: `_shared/config.py` and
  `_shared/llm_client.py` give every project the same required-key
  enforcement and multi-provider (Anthropic/OpenAI/Groq) switching, instead
  of each project reinventing it.
- **Project-specific overrides**: any `projects/<slug>/.claude/skills/` or
  `.claude/agents/` you add take precedence over the generic ones in this
  for that project only — useful if a project needs a recurring, bespoke
  step (see §3's suggestion).
- **Full validation**: `python scripts/validate_coding_agent_demo.py`
  checks every `projects/`, `concepts/`, and `teaching/` unit has its
  required files — run it any time, it's read-only.
- **Codex compatibility**: the same skills/agents/prompts are mirrored for
  Codex under `AGENTS.md`, `skills/`, `agents/`, `prompts/`, and
  `.codex-plugin/`. The `.claude/` versions (which this guide describes)
  are untouched and remain the source of truth for Claude Code.

---

## Quick reference

| I want to... | Run |
|---|---|
| Build a shippable app | `/new-project <slug>` → `/run-pipeline projects <slug>` |
| Build a certification-grade concept notebook | `/new-concept <slug>` → `/run-pipeline concepts <slug>` |
| Build a quick demo notebook/script | `/new-teaching-demo <slug>` → `/run-teaching-pipeline <slug>` |
| Extend an existing quick demo | `/add-teaching-step <slug> [<feature description>]` (repeat as needed) |
| Extend an existing project/concept | Just ask directly, referencing the folder |
| Check what's actually done | `/status-project <kind> <slug>` |
| Re-run just the tests | `/test-project <kind> <slug>` |
| Validate the whole repo's structure | `python scripts/validate_coding_agent_demo.py` |
