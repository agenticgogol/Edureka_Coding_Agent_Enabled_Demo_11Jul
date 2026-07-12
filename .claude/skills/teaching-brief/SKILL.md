---
name: teaching-brief
description: Use to start a lightweight teaching demo — a progressive sequence of small steps (e.g. "a) basic API call, b) add system prompt, c) add tool calling, d) add memory, e) basic RAG"), as notebook or small project. Drafts teaching/<slug>/teaching_brief.md through a sequence of gated checkpoints, ending only once the user has approved format, happy-path test case, env keys, observability, and vector store.
---

# Teaching Brief

For live-teaching or classroom demos, not certification-grade course
content. If you want a polished, fully-contracted atomic concept notebook
for the course itself, use `write-concept-brief` under `concepts/`
instead — this skill is for quick, progressive, instructor-driven demos,
now including full-stack (Streamlit + FastAPI) teaching builds, not just
notebooks.

Called by `/run-teaching-pipeline` right after the folder exists (from
`/new-teaching-demo`) and *before* `teaching-build` runs. This skill owns
every checkpoint up to "ready to generate code" — `run-teaching-pipeline`
does not skip or reorder these.

## When to use

- Right after `/new-teaching-demo <slug>` creates the folder, as the first
  real stage of `/run-teaching-pipeline`.
- The user wants to demonstrate a *sequence* of related concepts that
  build on each other in one sitting, or a small full-stack demo app.

## Procedure — run every step below, in order, each one a real stop

### 1. Get the project description

Ask the user for a project description in their own words — open-ended,
no format constraints on their answer. Accept anything from a one-line
idea to a dense multi-sentence technical spec (frontend/backend/provider/
vector-db details all in one paragraph is common and welcome).

If `teaching_brief.md` already exists, treat it as resumable state. Do not
re-ask for a description or checkpoint that is already recorded and
approved; restate what is known, then continue from the first missing or
unapproved checkpoint. This matters when Claude Code started the pipeline
and Codex is asked to finish it, or vice versa.

### 2. Parse it and clarify only the real gaps

Same discipline as `write-project-brief`'s freeform-description handling:
build two lists silently — what the description already answers (don't
re-ask these, just restate them for confirmation) and what's genuinely
open. For open items, ask with concrete options and a recommended default
rather than an open question, batched into one numbered message. Do not
proceed until answered.

### 3. Format — notebook vs full production setup

If the description already states this, skip straight to restating it for
confirmation. Otherwise ask explicitly:

> "Do you want this as (a) a Jupyter notebook / progressive script — fast
> to build, best for a step-by-step live walkthrough, or (b) a full
> Streamlit frontend + FastAPI backend, production-style setup?"

Record the answer as `Format:` in the brief. This determines which mode
`teaching-build` runs in later.

### 4. Happy-path test case — from the user's flow, not the code's

Once format is settled, draft **one** plain-language happy-path scenario
written from the end user's point of view — what they'd do and what
they'd see, not implementation detail. Example: "User opens the app,
picks 'Anthropic' and a model, types a question, clicks send, and sees a
streamed response with no error." Show it to the user and **wait for
explicit approval or correction** before continuing. This is the
lightweight track's equivalent of `write-and-validate-tests`'s
confirmation gate — one scenario, not a full test list, but still a real
stop.

### 5. Confirm .env has the required key(s)

Ask the user to confirm they've added the required provider key(s) (and,
if a vector store needing credentials is chosen in step 7, those too) to
`.env`. Whatever they answer, still run `require-api-key` for real — a
"yes" is not itself verification, it's what triggers the actual check.
**Hard stop** if the real verification call fails; do not proceed on the
user's word alone.

### 6. Observability — Phoenix or not

If the description already said whether to use Phoenix tracing, restate
it and move on. Otherwise ask: "Do you want Phoenix observability/tracing
wired in, or skip it for this demo?" Record the answer as
`Observability:` in the brief (`phoenix` or `none`).

### 7. Vector store — ask unless already specified

If the description already names a vector store or explicitly says no
retrieval/vector database is needed, restate that and move on. Otherwise
ask whether to use **ChromaDB** (local, zero setup), **FAISS** (local,
in-memory/file, fastest to demo), **Qdrant Cloud** (needs
`QDRANT_URL`/`QDRANT_API_KEY` in `.env`), or **none**. If Qdrant Cloud is
chosen after step 5 already verified the LLM key, run a separate
credential verification before building. Record the answer as
`Vector store:` in the brief.

### 8. Ready to generate?

Summarize everything decided so far (steps 1-7) in one short block and
ask: "Ready for me to generate the code?" Do not start `teaching-build`
before an explicit yes.

## Brief file

Create/update `teaching/<slug>/teaching_brief.md` — treat this as a
**living log** since the demo will likely grow throughout the day via
`teaching-add-step`:

```markdown
# Teaching Brief: <Name>

## Description (as given by user)
<verbatim or lightly cleaned-up description>

## Steps (in order, each builds on the previous)
a) <step> — added <date/session>
b) <step> — added <date/session>
...

## Format
notebook | full_app (streamlit + fastapi)

## Happy-path test case (user-approved)
<the one scenario, plain language>

## Observability
phoenix | none

## Vector store
chromadb | faiss | qdrant | none

## Constraints
<library/provider requirements — which provider key(s) required, plus
vector-store credentials if applicable>

## Audience level
<beginner / intermediate / advanced>

## Decisions
<anything the user said "your call" on — recorded so it isn't re-asked>

## Checkpoint status
- Description: approved | pending
- Clarifications: approved | pending | not needed
- Format: approved | pending
- Happy-path test case: approved | pending
- API key verification: verified | pending | failed
- Observability: approved | pending
- Vector store: approved | pending
- Ready to generate: approved | pending
- Build: complete | pending
- Verify: complete | pending | failed
```

Every checkpoint above (format, happy-path test case, .env confirmation,
observability, vector store, ready-to-generate) must show real user
approval in the conversation before `run-teaching-pipeline` moves to
`teaching-build` — do not infer approval from silence.
