---
name: write-project-brief
description: Use when the user wants to start a new end-to-end project but only has a rough idea, not a written project_brief.md. Interviews the user and drafts projects/<slug>/project_brief.md.
---

# Write Project Brief

Turn a rough idea into a `project_brief.md` the rest of the workflow can
build from. This is the *only* skill allowed to write into `project_brief.md`
before the user has approved it — never invent one silently.

## When to use

- User says something like "let's build an X app" with no brief file yet.
- A `project_brief.md` exists but is clearly a stub (a title and nothing else).

## Handling a detailed freeform description

Users often don't give a rough one-liner — they paste a dense, technical
paragraph that already answers most of the questions below in passing
("Streamlit frontend, FastAPI backend, keys from `.env`, must support
OpenAI/Anthropic/Gemini/Groq and switch behavior by provider..."). Treat
that as a gift, not noise:

1. Before asking anything, parse the description line by line and build two
   lists silently:
   - **Already specified** — every explicit decision (framework, provider(s),
     chunking strategy, vector DB, UI behavior, file types, etc.). Do not ask
     about anything on this list — restate it instead so the user can correct
     you if you misread it.
   - **Still open** — anything the workflow needs that the description didn't
     cover (auth model, error handling expectations, hosting target, exact
     model defaults per provider, embedding dims, retrieval top-k, chunk
     size/overlap, hybrid search weighting, non-goals, etc.).
2. Only ask about the "still open" list. For each open item, prefer a
   concrete multiple-choice framing over an open question — give 2-4
   plausible options plus a recommended default, e.g. "Chunk size: 500/1000/
   1500 tokens? Recommend 1000 with 150 overlap for PDF/URL mixed content
   unless you have a reason otherwise." This lets the user answer with a
   word instead of writing a spec.
3. Batch all open-item questions into one message, numbered, grouped by
   topic (frontend, backend, data/storage, provider/model, non-goals) rather
   than firing them one at a time.

## Procedure

1. If the user's request is already a detailed technical description, run
   "Handling a detailed freeform description" above first. Otherwise ask,
   one question at a time or as a short batch, for:
   - What problem does this solve, and for whom (technical or non-technical
     end user)?
   - What does "done" look like — the one demo scenario that must work?
   - Any explicit tech constraints (framework, must-use API, must avoid paid
     services)?
   - Any explicit non-goals (things it should *not* do)?
2. Do not fill gaps with assumptions — if the user says "not sure," leave it
   open and flag it for the `clarify-requirements` skill later rather than
   guessing. Never re-ask something the user's original description already
   answered.
3. Create `projects/<slug>/project_brief.md` with this shape:

```markdown
# Project Brief: <Name>

## Problem
<who has this problem, why it matters>

## Goal / Definition of Done
<the one scenario that proves it works>

## Users
<technical / non-technical / both>

## Constraints
<tech stack requirements, must-avoid, budget/API constraints>

## Non-goals
<explicitly out of scope>

## Open questions
<anything still unresolved — clarify-requirements picks these up>
```

4. Show the drafted brief to the user for approval before moving to
   `clarify-requirements` or `technical-design`.
