---
name: write-and-validate-tests
description: Use right after design.md is approved and before build steps begin. Drafts test cases from the clarified brief/design, shows them to the user for confirmation that they actually reflect intent, then implements and runs them as build proceeds.
---

# Write and Validate Tests

Test cases written by the same agent that then writes the implementation
can silently encode the same misunderstanding twice. This skill's defining
feature is a human checkpoint: the user reviews and confirms the test
cases match their intent *before* any test or implementation code is
written — not just before code review at the end.

## When to use

- Every project with a `design.md` — right after design is approved,
  before `make-plan`'s build steps start (test cases should exist before
  implementation, not be reverse-engineered from it afterward).
- For concepts: use a lighter version — the notebook's own "Exercise" +
  "Expected Output" sections (from `notebook-concept`) can serve this role;
  don't duplicate a separate test suite for a single-notebook concept
  unless it has real branching logic worth testing.

## Procedure

1. From `project_brief.md`'s "Definition of Done" and `design.md`'s API
   contract, draft a list of test cases in plain language first — not code
   yet. Cover:
   - The golden-path scenario from the brief.
   - Each documented API endpoint/agent behavior, happy path.
   - Edge cases implied by the brief (empty input, not-found, unauthorized).
   - Any safety-relevant case flagged by `security-check` (e.g. "rejects a
     destructive SQL attempt") if that skill applies to this project.
2. **Show this plain-language list to the user and ask them to confirm it
   actually reflects what they meant by the brief** — explicitly ask "does
   this list of scenarios match what you expect this project to handle
   correctly, and is anything missing or wrong?" Do not skip this even if
   the list looks obviously correct to you; the point is catching cases
   where your reading of the brief diverges from the user's intent.
3. Only after user confirmation, implement the test cases as real,
   runnable tests (`pytest` for backend/agent, `vitest`/`jest` for
   frontend) under `backend/tests/` and/or `frontend/tests/`.
4. Tests are written before or alongside implementation. Whoever is
   building the corresponding slice (`backend-builder`, `frontend-builder`,
   `agent-builder`) runs their own new tests immediately after writing that
   slice and fixes failures before moving to the next `plan.md` step — a
   failing test blocks progress, it doesn't get deferred to the end.
5. **Final test gate is owned by `run-tests`** (separate skill), invoked by
   `integrator` after all components are built, before
   `lint-and-typecheck`. This skill only drafts, confirms, and seeds
   initial per-slice test runs — it is not the thing that certifies "all
   tests pass" for the whole project; `run-tests` is.
6. `run-and-verify`'s end-to-end check is complementary, not a replacement:
   `run-tests` proves individual behaviors are correct in isolation;
   `run-and-verify` proves the whole assembled system actually runs.
