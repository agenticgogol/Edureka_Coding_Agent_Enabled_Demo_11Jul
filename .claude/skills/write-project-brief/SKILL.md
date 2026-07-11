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

## Procedure

1. Ask the user, one question at a time or as a short batch, for:
   - What problem does this solve, and for whom (technical or non-technical
     end user)?
   - What does "done" look like — the one demo scenario that must work?
   - Any explicit tech constraints (framework, must-use API, must avoid paid
     services)?
   - Any explicit non-goals (things it should *not* do)?
2. Do not fill gaps with assumptions — if the user says "not sure," leave it
   open and flag it for the `clarify-requirements` skill later rather than
   guessing.
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
