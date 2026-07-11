---
description: Run the full test gate for an existing project/concept and report real pass/fail — the run-tests skill, callable standalone at any time.
argument-hint: <projects|concepts> <slug>
---

Parse `$ARGUMENTS` as `<kind> <slug>` (kind is `projects` or `concepts`).

1. Confirm `$1/$2/plan.md` exists; if not, tell the user this unit hasn't
   been planned yet and stop (nothing to test against).
2. Invoke the `run-tests` skill against `$1/$2/`: run the full test suite
   (backend/agent `pytest`, frontend `vitest`/`jest`, whichever exist),
   capture real output, and report exact pass/fail counts plus the name
   and reason for every failure — never report "tests pass" without having
   just executed them in this call.
3. If failures exist, fix the implementation (or, only if a test
   contradicts user-confirmed intent from `write-and-validate-tests`, flag
   that discrepancy to the user rather than silently changing the test)
   and re-run until green or explicitly documented skips remain.
4. Update `$1/$2/README.md`'s "Testing" section with the final run output
   and command used.

This command can be run standalone, independent of the full pipeline —
useful after a manual edit to re-certify the test gate.
