---
name: teaching-brief
description: Use to start a lightweight teaching demo — a progressive sequence of small steps (e.g. "a) basic API call, b) add system prompt, c) add tool calling, d) add memory, e) basic RAG"), as notebook or small project. Drafts teaching/<slug>/teaching_brief.md through a sequence of gated checkpoints, ending only once the user has approved format, happy-path test case, env keys, observability, vector store, and any MCP tools (checking for free public MCP servers before assuming custom tool code).
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

If a vector store was chosen (not `none`), ask one follow-up before moving
on: **"Should retrieval be a single fixed retrieve-then-answer step, or
does the agent need to decide whether/how many times to retrieve, grade
what it gets back, and retry on a bad result?"** Give a concrete example
from the description if one exists. Record the answer as `RAG mode:` in
the brief (`fixed` or `agentic`). If `agentic`, also ask which optional
capabilities are in scope beyond the always-on core (retrieval decisions +
self-grading): multi-tool routing, multi-hop planning, reranking,
groundedness verification, abstention — batch these as one closed-ended
list, don't wire any silently, and record the confirmed subset as
`Agentic RAG capabilities:` in the brief. This is what `teaching-build`
uses to decide between `vector-store` alone vs. `agent-agentic-rag`.

### 8. External tools — prefer a free public MCP server over custom tool code

From the description, list any tool/capability the demo needs beyond the
LLM provider and vector store — including things that would normally be
hand-coded (filesystem access, git commands), not just obvious
third-party calls (web search, GitHub, Slack, sending email, etc.). If
none, record `MCP tools: none` and move on — don't invent a tool need.
For each one found, do a live lookup (same idea as
`agent-decision-external-tool-sourcing`'s step 1, lightweight for this
track): search for a free public MCP server that already exposes it. If
one is found, **recommend it by default** rather than presenting a neutral
choice — tell the user plainly: **"There's a free public MCP server for
[capability]: [server name], via [stdio package / hosted endpoint]. I'd
use this by default rather than writing custom tool code — any reason
you'd rather skip it or keep the demo simpler?"** — and record the choice.
This is a demo, not a production build, so declining and simplifying scope
is still a completely fine answer; the preference for MCP doesn't mean
pushing the user into wiring a tool the demo doesn't actually need — it
means defaulting to the free existing server over hand-written code
*when* a tool is wanted at all. Record the answer as `MCP tools:` in the
brief (server name(s) used, or `none`/`declined`).

### 9. Ready to generate?

Summarize everything decided so far (steps 1-8) in one short block and
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

## RAG mode
fixed | agentic | n/a (no vector store)

## Agentic RAG capabilities (only if RAG mode = agentic)
core: agentic retrieval decisions, self-grading/self-correction (always on)
optional: <subset of multi-tool routing / multi-hop planning / reranking /
groundedness verification / abstention actually confirmed, or "none">

## MCP tools
<server name(s) chosen, with transport (stdio package / hosted endpoint),
or "none" / "declined (found [server], user chose to skip)">

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
- RAG mode: approved | pending | n/a
- MCP tools: approved | pending
- Ready to generate: approved | pending
- Build: complete | pending
- Verify: complete | pending | failed
```

Every checkpoint above (format, happy-path test case, .env confirmation,
observability, vector store, MCP tools, ready-to-generate) must show real
user approval in the conversation before `run-teaching-pipeline` moves to
`teaching-build` — do not infer approval from silence.
