---
description: Create the folder for a new teaching demo under teaching/. Does not interview, draft a brief, or write code — that's what /run-teaching-pipeline does next.
argument-hint: <teaching-slug>
---

The user wants a teaching demo with slug `$ARGUMENTS` under `teaching/`.
This command's only job is to create the workspace so
`/run-teaching-pipeline $ARGUMENTS` has somewhere to write to — it does not
ask questions or draft anything.

1. If `teaching/$ARGUMENTS/` already exists and has a `teaching_brief.md`,
   read it and report its current state instead of overwriting anything —
   tell the user whether to resume via `/run-teaching-pipeline $ARGUMENTS`
   (if the brief isn't fully approved yet) or use `/add-teaching-step
   $ARGUMENTS` (if it's already built and they want to extend it).
2. Otherwise, create the empty `teaching/$ARGUMENTS/` folder.
3. Tell the user to run `/run-teaching-pipeline $ARGUMENTS` next — that
   command is where the actual project description, clarifying questions,
   format choice, and every other checkpoint happen.
