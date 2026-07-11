---
description: Start a new end-to-end project — drafts project_brief.md and stops for review, does not build code yet.
argument-hint: <project-slug>
---

The user wants to start a new project with slug `$ARGUMENTS` under
`projects/`.

1. If `projects/$ARGUMENTS/project_brief.md` already exists, read it and
   report its current state instead of overwriting it — ask the user if
   they want to revise it or proceed to `/clarify-project $ARGUMENTS`.
2. Otherwise, create the folder and use the `write-project-brief` skill to
   interview the user and draft `projects/$ARGUMENTS/project_brief.md`.
3. Show the drafted brief and stop — do not proceed to clarification,
   design, or code in this command. Tell the user to run
   `/clarify-project $ARGUMENTS` next (or `/run-pipeline projects $ARGUMENTS`
   to run the whole thing end to end with checkpoints).
