# projects/

One folder per end-to-end application, created one at a time.

To start a new project:

1. Create `projects/<slug>/`.
2. Add `project_brief.md` (use the `write-project-brief` skill if you want
   Claude to draft it with you).
3. Tell Claude Code: "read `projects/<slug>/project_brief.md` and start the
   workflow" — it will follow `../CLAUDE.md`: clarify, design, plan, build,
   integrate, verify.

Each project folder ends up self-contained: brief, `design.md`, `plan.md`,
`frontend/`, `backend/`, and a `README.md` with the single command to run
it.

Do not generate multiple project folders in one pass — one project at a
time, validated with `../scripts/validate_coding_agent_demo.py` before
starting the next.
