---
description: Start a new lightweight, progressive teaching demo (notebook or small project) — drafts teaching_brief.md and stops for review.
argument-hint: <teaching-slug>
---

The user wants a teaching demo with slug `$ARGUMENTS` under `teaching/`.
This is the lightweight track — for progressive, instructor-driven demos
(e.g. "a) basic API call, b) add system prompt, c) add tool calling, d)
add memory, e) basic RAG"), not the full certification-grade pipeline used
by `projects/`/`concepts/`.

1. If `teaching/$ARGUMENTS/teaching_brief.md` already exists, read it and
   report its state instead of overwriting it.
2. Otherwise, create the folder and use the `teaching-brief` skill to
   interview the user: ordered list of steps, notebook vs script/project
   format, constraints, audience level.
3. Show the drafted brief and stop. Tell the user to run
   `/run-teaching-pipeline $ARGUMENTS` to build it.
