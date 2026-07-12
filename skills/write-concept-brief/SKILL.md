---
name: write-concept-brief
description: Use when the user wants a new atomic concept demo (notebook-scale, one idea only) but only has a rough idea, not a written concept_brief.md. Interviews the user and drafts concepts/<slug>/concept_brief.md.
---

# Write Concept Brief

Same spirit as `write-project-brief` but scoped to a single atomic concept
(one notebook or one small script — not a multi-part app).

## When to use

- User wants to demo/teach one idea (e.g. "embeddings intuition", "ReAct
  loop trace") and no `concept_brief.md` exists yet.

## Handling a detailed freeform description

If the user pastes a detailed description rather than a rough idea, parse it
first: list what it already answers (library/API, provider, expected
behavior) versus what's genuinely missing. Don't ask about anything already
stated — restate it for confirmation instead. For genuine gaps, ask with
concrete options and a recommended default rather than an open question
(e.g. "prior knowledge level: assumes learner knows Python basics but not
embeddings — correct?"). Batch all gap questions into one numbered message.

## Procedure

1. If given a detailed description, run "Handling a detailed freeform
   description" above first. Otherwise ask:
   - What is the one concept being taught? (must be a single idea — if the
     user describes 2+ concepts, tell them to split into multiple concept
     folders)
   - What prior knowledge does the learner already have?
   - What is the "aha" moment / expected output that proves understanding?
   - Any specific library/API required or forbidden?
2. Create `concepts/<slug>/concept_brief.md`:

```markdown
# Concept Brief: <Name>

## Concept
<the single idea, one sentence>

## Prerequisite knowledge
<what the learner already knows>

## Learning outcome
<what "got it" looks like — the aha moment>

## Constraints
<library/API requirements, which provider key is required>

## Open questions
```

3. Confirm with the user before handing off to `clarify-requirements` /
   `technical-design`.
