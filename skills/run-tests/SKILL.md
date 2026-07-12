---
name: run-tests
description: Use after all components are built, before lint-and-typecheck. The single owner of "did the tests from write-and-validate-tests actually pass" — runs the full suite, captures real output, and blocks progress on any failure. Owned by the integrator subagent.
---

# Run Tests

This is the explicit answer to "who validates the test cases passed." No
other skill certifies this — `write-and-validate-tests` drafts and seeds
tests; individual builders run *their own* new tests as they go; this
skill is the one full-suite run that counts as the project's test gate.

## When to use

- Always, after `frontend-builder`/`backend-builder`/`agent-builder` have
  all finished, before `lint-and-typecheck`. Owned by `integrator`.
- Re-run any time a later step (security fix, integration fix) touches
  code covered by existing tests.

## Procedure

1. Run the full suite for every component that has one:
   - Backend/agent: `pytest backend/tests/ -v`
   - Frontend: `npm test` / `vitest run` / `jest`
2. Capture and report the **actual output** — pass count, fail count, and
   the name + failure reason of every failing test. Never report "tests
   pass" without having actually executed them in this step; a claim
   based on earlier per-slice runs during build is not sufficient, because
   integration/security/other fixes since then may have broken something.
3. If anything fails, invoke `project-debug` to reproduce, diagnose, and
   fix it (preferred), rather than one-shot guessing — it will fix the
   implementation, or, only if the test itself was wrong (rare, and only
   if the drafted case actually contradicts the user-confirmed intent from
   `write-and-validate-tests` step 2), fix the test and flag that
   correction back to the user rather than silently changing what was
   confirmed. Re-run the full suite again after each fix. Do not proceed
   to `lint-and-typecheck` until 100% pass, or until any skipped/xfail
   test has an explicit, documented reason.
4. Record the final run output (pass/fail counts, command used) in the
   project README's "Testing" section, and mark the corresponding
   `plan.md` checklist item complete only once this step has actually run
   clean.
5. This is a distinct gate from `run-and-verify` — this proves individual
   behaviors are correct in isolation; `run-and-verify` proves the whole
   assembled system works end to end. Both must pass.
