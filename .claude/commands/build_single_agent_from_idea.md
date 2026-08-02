---
description: Turn a short single-agent project idea into a comprehensive project_brief.md — asks fixed clarifying questions (frontend/backend/api/input/output/tools), runs agent architecture design, and assembles a brief detailed enough for a coding agent to build end-to-end. Does not write code.
argument-hint: <single-agent project idea, pasted freeform>
---

The user has pasted a single-agent project idea: `$ARGUMENTS`

Your job in this command is to turn that idea into one comprehensive
`projects/<slug>/project_brief.md` that a coding agent (this one or another)
can build from with `/run-pipeline projects <slug>` — **and stop there**. Do
not draft `design.md`, do not write code, do not run `require-api-key`. This
command only produces the brief.

## Step 0 — Slug and scope check

Derive a short `<slug>` from the idea (kebab-case, e.g. `it-ticket-triage`).
If `projects/<slug>/project_brief.md` already exists, read it and ask the
user whether they want to revise it or start over, instead of silently
overwriting.

Confirm this is in fact a **single-agent** architecture candidate (one
bounded agent — ReAct, memory-augmented ReAct, plan-execute-replan,
self-evaluating workflow, or classifier-router — not a multi-agent
system). If the idea clearly needs multiple specialized agents
coordinating, say so and point the user at `/agent-system-design` directly
without the single-agent framing — don't force-fit it.

## Step 1 — Parse what the idea already answers

Before asking anything, read `$ARGUMENTS` line by line and build two lists
silently, same discipline as `write-project-brief`:

- **Already specified** — anything the idea states or clearly implies
  (a named provider, "no paid APIs," a specific data source, a UI
  preference, etc.). Don't ask about these — restate them so the user can
  correct a misread.
- **Still open** — everything the checklist below needs that the idea
  didn't cover.

## Step 2 — Fixed clarifying checklist

Ask only the "still open" items from this checklist, batched in one
numbered message, grouped by category. For every item with a defensible
default, give 2-4 concrete options plus a recommended default and a
one-line reason — never a bare open-ended question when options exist.
Only the first two rows (problem/done) are genuinely open-ended.

1. **Problem & user** — what problem does this solve, and for whom
   (technical or non-technical end user)? What does "done" look like — the
   one demo scenario that must work end to end?
2. **Input** — what does the agent receive per invocation (free text,
   structured form, file upload, webhook payload, scheduled trigger)? What
   shape/format exactly (e.g. CSV columns, JSON schema, file types)?
3. **Output** — what does the agent produce (chat reply, structured JSON,
   a written file, a DB write, an action taken on an external system)? Does
   it need to be shown to a human before taking effect (HITL), or can it
   act autonomously?
4. **Tools** — what does the agent need to call to do its job (DB
   read/write, vector search, file parsing, a specific external API, a
   calculator/deterministic function)? For each: read-only or read/write?
   Free/local option or does it require a paid API? (If unsure, flag it —
   Step 4 below resolves this via `agent-decision-external-tool-sourcing`
   if the staged design path is chosen.)
5. **Frontend** — Streamlit (simple, this repo's default for demos) /
   Next.js (production-style) / notebook only (no UI, this repo's fastest
   path for a single-agent teaching-style build) / none (API only)?
   Recommend Streamlit unless the idea implies a production app.
6. **Backend/API** — FastAPI backend behind the frontend, or is the
   agent logic called in-process (no separate API layer, appropriate for
   a notebook or a single-process Streamlit app)? Recommend in-process
   unless the idea implies multiple clients or an external integration
   needs to call it directly.
7. **Memory** — does it need to remember anything across invocations
   (user-specific mappings, conversation history, past corrections), or is
   every invocation stateless? If yes, roughly what shape (key-value,
   vector store of past examples, full transcript)?
8. **Provider/model** — which LLM provider (Anthropic default via
   `_shared/llm_client.py` unless stated otherwise)? Confirm no paid tools
   beyond the LLM call itself are required, or list which paid ones are
   accepted and why.
9. **Non-goals** — anything explicitly out of scope, so the coding agent
   doesn't over-build.

Do not fill any of these with silent assumptions. If the user says "your
call," record the recommended default explicitly as a decision, not as an
unstated guess.

**Every recommendation must be specific to this idea, not a generic
category default.** For tools/input/output/memory in particular, don't
just present the category options above — infer a concrete first-draft
answer from `$ARGUMENTS` itself (e.g. for "IT ticket triage," propose
"input: ticket text + optional attachment; tools: KB vector search
(local Chroma), ticket-system write (SQLite)" rather than a bare menu of
possibilities) and present it as "here's what I'd propose, tell me what's
wrong" — this is faster for the user to correct than to construct from
scratch, and it's what makes this a co-creation rather than a form.

## Step 2a — When the user is unsure

If the user answers "I don't know," "not sure," "you decide the details,"
or gives a vague/partial answer to any item, do not just fall back to
recording a default silently. Actively help:

1. Offer 2-3 concrete, idea-specific suggestions (not generic examples) —
   ground them in how similar use cases are typically built. If this repo
   has `teaching/langgraph_basics/single_agent_architectures/
   single_agent_usecase_example.ipynb`, check it for a comparable use case
   and reference the pattern it uses as a starting point.
2. Ask one narrower follow-up question to pick between those 2-3, rather
   than re-asking the original broad question.
3. Only once the user still declines to choose, record the top suggestion
   as an explicit "your call" default in `## Decisions` — never leave it
   as a silent guess, and never leave it as a genuinely open question
   either (see Step 4's `## Open Questions`, which should stay empty).

Repeat Step 2 / 2a across as many rounds as needed — this is a
conversation, not a one-shot form. Don't force everything into a single
batched message if the user's answers open up new sub-questions; ask
follow-ups in the same grouped, options-with-default style until every
item is either confirmed, corrected, or resolved via 2a.

## Step 3 — Architecture design

Ask the user to choose:

- **Staged** (`agent-system-design`) — the full 8-stage gated pipeline,
  each stage approved individually. Recommended if the user wants to see
  the reasoning behind each decision, or if tools/memory/loop design are
  non-trivial.
- **One-shot** (`agent-architecture-design`) — a single interview producing
  one `architecture_design.md`-equivalent directly. Recommended for a
  small, clearly-bounded single-agent build where Step 2's answers already
  make the pattern obvious.

Feed the answers from Step 2 into whichever is chosen as pre-answered
context so it doesn't re-ask what's already settled. Run it to completion
(through explicit approval, for the staged path) before continuing.

This step produces `projects/<slug>/system_design/` (staged) or an
equivalent one-shot design doc — the source of truth for the agent
pattern, tool inventory + authorization, memory, context engineering, loop
engineering, and eval/security/guardrails decisions that Step 4 folds into
the brief.

## Step 4 — Assemble the comprehensive project brief

Write `projects/<slug>/project_brief.md`. This must be self-sufficient —
a coding agent building from this file alone (plus the referenced design
doc) should never have to guess. Use this shape:

```markdown
# Project Brief: <Name>

## Problem & User
<from Step 2.1>

## Definition of Done
<the one demo scenario from Step 2.1, stated concretely and testably>

## Architecture Summary
<pattern chosen in Step 3 (ReAct / memory-augmented ReAct / plan-execute-replan /
self-evaluating workflow / classifier-router), one paragraph on why, and a
pointer to the full design doc from Step 3>

## Input Contract
<exact shape from Step 2.2>

## Output Contract
<exact shape from Step 2.3, including HITL requirement if any>

## Tools
<table: tool name | purpose | read-only or read/write | free/local or paid
(and if paid, approved alternative per Step 2.4) | maps to which design-doc
tool entry>

## Frontend
<choice from Step 2.5, and what it must render/collect>

## Backend / API
<choice from Step 2.6>

## Memory
<from Step 2.7 — what's stored, where, lifetime>

## Provider / Model
<from Step 2.8 — provider, model default, key env var name>

## Non-Goals
<from Step 2.9>

## Decisions
<any "your call" defaults the user accepted, recorded explicitly>

## Open Questions
<should be empty by the time this is written — if anything remains, it
must be resolved before stopping, not left for `clarify-requirements` to
re-discover>

## Reference
- Architecture design: `projects/<slug>/system_design/architecture_design.md`
  (or equivalent one-shot doc)
```

Before writing the file, show this assembled draft to the user as a
whole and explicitly invite edits section by section ("anything here you
want to change before I save it?") — this is the co-creation checkpoint,
not a rubber stamp. If the user redirects any section, revise it and
show the change back before continuing; don't silently patch and move on.
Only write the file once the user confirms it's ready.

## Step 5 — Stop and hand off

Do not proceed to `technical-design`, `require-api-key`, or any build
step. Tell the user:

- The brief and architecture design are ready.
- Next step: `/run-pipeline projects <slug>` to run clarify → design → tests
  → build → verify end to end (clarify-requirements will run again but
  should find nothing open, since Step 2 already resolved it).

## Ground rules

- Never skip Step 2's checklist categories, even if the idea sounds
  simple — a coding agent building from an incomplete brief will guess,
  and guesses are exactly what this command exists to eliminate.
- Never invent tool/API choices without flagging paid-vs-free — this repo
  never spends money without explicit approval, and that includes tools
  named inside a project brief that a later build step will wire up
  unquestioningly.
- If Step 3's design process surfaces a conflict with an answer from Step
  2 (e.g. user said "no memory needed" but the chosen pattern requires
  it), stop and resolve the conflict with the user before writing the
  brief — don't silently pick one side.
- This command produces exactly one brief per invocation, for one project.
