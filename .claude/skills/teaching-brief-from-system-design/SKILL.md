---
name: teaching-brief-from-system-design
description: Use after an architecture design (staged system_design/ or one-shot architecture_design.md) is approved for a teaching demo, to draft the initial teaching/<slug>/teaching_brief.md so it honors every relevant system-design decision instead of re-deriving them. Does not itself get final checkpoint approval — teaching-brief still runs afterward for that.
---

# Teaching Brief From System Design

The teaching track (`teaching-brief`) and the agent-system-design track
(`agent-architecture-design` / `agent-system-design`) were built
independently and don't know about each other: `teaching-brief` asks its
own format/happy-path/observability/vector-store questions from scratch,
even when a full architecture design was already produced for the exact
same use case. This skill is the bridge — it translates an approved
architecture design's decisions into `teaching-brief`'s pre-answered
context, so its checkpoint procedure has nothing left to *derive*, only
to confirm.

## When to use

- Called by `/agent_system_design_to_build_onego` right after its
  architecture-design stage (staged or one-shot) is approved, before
  `teaching-brief` runs.
- Not useful standalone — it assumes an approved architecture design
  already exists and produces a draft, not a finished, approved brief.

## Inputs this skill needs

1. The approved architecture design: either
   `teaching/<slug>/architecture_design.md` (one-shot) or
   `teaching/<slug>/system_design/architecture_design.md` (staged,
   post-assembly) plus its eight stage files for detail lookups.
2. The raw usecase description and any requirements-checklist answers
   already gathered by the calling command (problem/user, input, output,
   tools, frontend, backend, memory, provider, non-goals) — passed in as
   arguments, not re-derived from the architecture doc alone, since the
   architecture doc may not capture UI/frontend framework choice (that's
   out of scope for `agent-architecture-design`, which focuses on the
   agent pattern, not the surrounding app shell).

## Procedure

### 1. Read the architecture design

Pull out, specifically:
- **Chosen architecture pattern** and its one-paragraph rationale (for
  `Description`).
- **Tool & side-effect boundaries** table (for `Constraints`, and to
  detect whether any tool is vector-store-backed).
- **Knowledge & state design** section (to detect whether RAG/vector
  retrieval is actually part of this system, vs. a transactional-tool or
  curated-context knowledge need that needs no vector store at all).
- **Runtime & deployment shape** (sync/async/batch/event-driven) — informs
  whether `full_app` is actually appropriate or whether this is better
  suited to a notebook (e.g. a batch/event-driven shape rarely makes
  sense as a interactive Streamlit demo).
- **Non-functional budgets & overlays** section — whether tracing/
  observability was flagged as required.
- **Evaluation & rollout gates** section — the concrete "ready to ship"
  scenario, which becomes the seed for the happy-path test case.

### 2. Map architecture decisions to `teaching_brief.md` fields

| architecture_design.md source | teaching_brief.md field | Mapping rule |
|---|---|---|
| Chosen architecture pattern + rationale | `Description` | Restate in plain language, crediting the pattern by name |
| Chosen pattern + calling command's Frontend/Backend answers | `Format` | `full_app` if the calling command's Frontend answer was Streamlit/Next.js or Backend was FastAPI; `notebook` if the answer was "notebook only" or the runtime shape is batch/offline |
| Evaluation & rollout gates' "ready to ship" scenario | `Happy-path test case` | Rephrase as one end-user scenario (what they'd type/click, what they'd see) — still needs human approval, this is only a draft |
| Non-functional budgets & overlays | `Observability` | `phoenix` if tracing/observability is called out as required; else `none` |
| Knowledge & state design + Tool inventory | `Vector store` | Name the specific store if a RAG/retrieval tool exists in the design; else `none` — never default to a vector store the architecture doc didn't actually call for |
| Tool & side-effect boundaries + Provider/model answer | `Constraints` | List required env vars: LLM provider key, plus any tool's credential requirements flagged as paid/external in the tools table |
| Calling command's Problem & User answer | `Audience level` | Infer from who the design doc says is affected (e.g. "non-technical stakeholders" -> beginner-facing; "on-call engineers" -> intermediate/advanced) |
| Any "your call" defaults recorded during the earlier requirements checklist | `Decisions` | Carry forward verbatim — don't re-ask |

### 3. Draft `teaching/<slug>/teaching_brief.md`

Use `teaching-brief`'s exact schema (see that skill's "Brief file"
section). Fill in `Description`, `Format`, `Happy-path test case`,
`Observability`, `Vector store`, `Constraints`, `Audience level`, and
`Decisions` per the mapping above. Add one extra line under `Description`
pointing back to the architecture doc:

```markdown
## Description (as given by user)
<mapped description>

Architecture: see `architecture_design.md` (or `system_design/architecture_design.md`)
for the full pattern rationale, tool inventory, memory design, and eval/
security overlays this brief builds from.
```

Set every checkpoint this skill filled to `pending` in `## Checkpoint
status` — **not** `approved**. This skill only drafts; it never marks a
checkpoint approved on the user's behalf. That happens when `teaching-brief`
runs next and gets real explicit confirmation on each pre-filled value
(restating it and asking "still correct?" rather than silently treating a
draft as consent, per `teaching-brief`'s own resume-state discipline).

### 4. Hand off

Report back to the calling command which fields were pre-filled from the
architecture design vs. left for `teaching-brief` to ask fresh (this
happens when the architecture doc genuinely doesn't determine an answer,
e.g. Format when the calling command never asked a Frontend question).
Do not run `teaching-build` or any later stage yourself — that is the
calling command's job once `teaching-brief`'s own checkpoints are all
approved.

## Ground rules

- Never mark a `teaching_brief.md` checkpoint `approved` from this skill
  — drafting is not approval, and `teaching-brief`'s hard-stop discipline
  (especially `require-api-key`) must still run for real.
- Never invent a Format, Observability, or Vector store answer the
  architecture design doesn't actually support — if the mapping in step 2
  is genuinely ambiguous, leave the field blank and let `teaching-brief`
  ask it fresh rather than guessing.
- If the architecture design's runtime shape conflicts with `full_app`
  (e.g. it explicitly calls for durable/event-driven execution), say so
  explicitly to the calling command rather than silently drafting
  `Format: full_app` anyway — a teaching demo can still simplify to a
  synchronous approximation, but that's a decision for the user to
  confirm, not this skill to assume.
