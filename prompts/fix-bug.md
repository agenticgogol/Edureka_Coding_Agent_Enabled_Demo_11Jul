---
description: User reports a bug in an already-built project/concept/teaching demo. Reproduces it, fixes it via the matching debug skill, and re-certifies the test gate and verify step.
argument-hint: <projects|concepts|teaching> <slug> <bug description>
---

Parse `$ARGUMENTS` as `<kind> <slug> <bug description>` (kind is
`projects`, `concepts`, or `teaching`; everything after the slug is the
bug report in the user's own words).

1. Confirm the unit was actually built already: for `projects`/`concepts`,
   `$1/$2/plan.md` must exist; for `teaching`, `$1/$2/teaching_brief.md`
   must exist AND have been through `teaching-build` at least once
   (notebook/`app.py`/backend+frontend files present). If not, tell the
   user this unit hasn't been built yet and stop — there's nothing to
   debug.
2. If the bug description is vague ("it doesn't work," "chat is broken"),
   ask the user for the minimum needed to reproduce it: what they did,
   what they expected, what actually happened (error text, wrong output,
   etc.) — don't start guessing at causes from a vague report.
3. Invoke the debug skill matching this unit against `$1/$2/` with that
   reproduction:
   - `projects`/`concepts` -> `project-debug`.
   - `teaching` with `Format: notebook` in `teaching_brief.md` ->
     `teaching-debug`.
   - `teaching` with `Format: full_app` -> `project-debug` (it already
     handles frontend/backend/contract issues).
   Whichever runs: reproduce the real failure, diagnose, fix one
   hypothesis at a time, re-run until the reported behavior actually
   works.
4. After the debug skill reports success:
   - `projects`/`concepts`: re-run `run-tests` (full suite) and, if the
     fix touched anything on the request path, `run-and-verify` — a bug
     fix isn't done until both are green again, not just the one reported
     symptom.
   - `teaching`: re-run `teaching-verify` (top to bottom for notebook, the
     full happy-path flow again for full_app) — same principle, one
     symptom fixed shouldn't mean skipping the rest.
5. Update `$1/$2/README.md`'s "Testing" section with what was wrong and
   what changed.

This command is for bugs found *after* the unit's pipeline already
reported success once. For failures during the initial build, the
pipeline's own test/verify stages already call the matching debug skill
automatically — you don't need this command for that.
