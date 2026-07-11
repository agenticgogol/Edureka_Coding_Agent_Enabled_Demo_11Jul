# concepts/

One folder per atomic, notebook-scale concept demo, created one at a time.

To start a new concept:

1. Create `concepts/<slug>/`.
2. Add `concept_brief.md` (use the `write-concept-brief` skill if you want
   Claude to draft it with you). One concept per folder — if the idea
   covers two or more distinct concepts, split it into separate folders.
3. Tell Claude Code: "read `concepts/<slug>/concept_brief.md` and start the
   workflow" — it will follow `../CLAUDE.md`: clarify, design, plan, build
   (via the `notebook-concept` skill), integrate, verify.

Each concept folder ends up self-contained: brief, `design.md`, `plan.md`,
`notebook.ipynb` (or `app.py` for a small demo app), and a `README.md`.

Do not generate multiple concept folders in one pass — one concept at a
time, validated with `../scripts/validate_coding_agent_demo.py` before
starting the next.
