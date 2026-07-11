---
description: Start a new atomic concept demo — drafts concept_brief.md and stops for review, does not build a notebook yet.
argument-hint: <concept-slug>
---

The user wants to start a new concept with slug `$ARGUMENTS` under
`concepts/`.

1. If `concepts/$ARGUMENTS/concept_brief.md` already exists, read it and
   report its current state instead of overwriting it.
2. Otherwise, create the folder and use the `write-concept-brief` skill to
   interview the user and draft `concepts/$ARGUMENTS/concept_brief.md`. If
   the user describes more than one concept, tell them to split into
   multiple concept folders — one concept per folder is a hard rule here.
3. Show the drafted brief and stop. Tell the user to run
   `/run-pipeline concepts $ARGUMENTS` to build it end to end.
