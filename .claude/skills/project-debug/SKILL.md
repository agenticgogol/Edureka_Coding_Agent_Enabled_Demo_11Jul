---
name: project-debug
description: Use whenever a project/concept's code fails during run-tests, run-and-verify, or in response to a user-reported bug after the app is already built. Iterates on the real error until it's fixed, rather than reporting failure once and stopping.
---

# Project Debug

The full-stack/notebook counterpart to `teaching-debug`. This is what
`run-tests` and `run-and-verify` call automatically on any failure, and
what `/fix-bug` calls when a user reports something broken after the
project was already verified. It doesn't stop at "here's the error" — it
keeps fixing until the failing behavior actually works, or until it's
genuinely blocked on something only the user can resolve.

## When to use

- A test fails during `run-tests`.
- The end-to-end request in `run-and-verify` fails.
- The user reports a bug in an already-built project/concept (via
  `/fix-bug` or directly in conversation).

## Procedure

1. **Reproduce first.** Never patch code based on a description alone —
   run the failing test, hit the failing endpoint, or drive the exact user
   flow that was reported, and capture the real traceback/response/log
   output.
2. **Scope the blast radius.** Is this one component (frontend, backend,
   agent/graph, notebook cell) or a contract mismatch between two of them
   (e.g. frontend calling an endpoint shape backend no longer returns)?
   Check `design.md`'s API contract section against what's actually
   implemented before assuming either side is "correct."
3. **Diagnose before editing**, cheapest checks first:
   - Missing/wrong import, dependency not installed -> check
     `requirements.txt`/`package.json` against what's actually imported.
   - API contract drift -> diff the frontend call against the backend
     route/response model in `design.md`; fix whichever side deviated.
   - Framework API mismatch on CrewAI/DSPy/MCP/GraphRAG -> run
     `research-first` and check current docs before guessing a fix; don't
     trial-and-error an API you're unsure of.
   - Missing/expired/rate-limited provider key -> hard stop, not a bug to
     code around. There is no mock mode. Tell the user exactly which key
     needs fixing and re-run `require-api-key` before continuing.
   - State issue (stale venv/node_modules, cached build) -> reinstall
     clean before assuming the code itself is wrong.
   - Data file missing/malformed -> check `data/` actually has what the
     code expects, per `data/README.md`.
4. **Fix one hypothesis, re-run immediately.** Don't batch multiple
   speculative fixes before testing; change one thing, re-run the
   reproduction from step 1, observe.
5. **Repeat** until the reproduction passes. No fixed retry limit — keep
   iterating on genuinely different hypotheses as long as each attempt is
   teaching you something new.
6. **When to stop and ask the user** instead of continuing to guess:
   - The fix requires a decision only the user can make (a missing key, a
     genuine ambiguity in what the correct behavior should be).
   - Several genuinely different hypotheses tried and the error hasn't
     changed in a way that suggests progress — report exactly what was
     tried, the current error, and what's needed to unblock it.
7. Once fixed, re-run the **full test gate** (`run-tests`) and, if the fix
   touched anything on the request path, `run-and-verify` too — a fix for
   one failure can silently break something that was passing before.
8. If this was a user-reported bug (not a build-time failure), record what
   was wrong and the fix in the project/concept README's "Testing" section
   so the history isn't lost.
