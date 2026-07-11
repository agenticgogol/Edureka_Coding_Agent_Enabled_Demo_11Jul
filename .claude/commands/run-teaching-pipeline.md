---
description: Build a progressive teaching demo end to end — the lightweight 3-stage pipeline (brief already drafted -> build -> verify), not the full projects/concepts pipeline.
argument-hint: <teaching-slug>
---

`$ARGUMENTS` is the teaching demo slug under `teaching/`.

This is intentionally a **3-stage pipeline**, not the 14-stage one used by
`/run-pipeline`. No `clarify-requirements`, no `write-and-validate-tests`
user-confirmation gate, no `security-check`/`eval-and-observability`/
`lint-and-typecheck`/`validate-env`/`integrate-and-assemble`/`deploy-config`
— those exist for shippable projects and certification-grade concepts,
not for a live classroom demo. If the user wants any of those added for a
specific teaching demo (e.g. they want a security-check because a step
demos SQL tool calls), they'll say so explicitly — don't add it by
default.

## Preconditions

- `teaching/$ARGUMENTS/teaching_brief.md` must exist. If not, stop and
  tell the user to run `/new-teaching-demo $ARGUMENTS` first.

## Stages

0. **Require API key** — `require-api-key`. **HARD STOP** if no provider
   key is set or it fails a real verification call. No mock mode exists
   in this repo — do not proceed to build until this passes.
1. **Build** — `teaching-build`. Generate the progressive notebook/script
   from `teaching_brief.md`'s ordered steps, each one visibly building on
   the last, each runnable on its own once prior cells/files have run,
   against the real verified provider.
2. **Verify** — `teaching-verify`. Run every step top to bottom against the
   real provider and confirm real output at each step. **On any failure,
   this stage automatically invokes `teaching-debug`** — it iterates on
   the real error until fixed, it does not stop at the first failure and
   report it. If the failure is the API key itself, that's a hard stop:
   report it and re-run `require-api-key`, don't work around it.
3. **Report** — summarize what was built, the exact run command, and which
   provider/model it was verified against. No formal review/deploy stage
   for this track.

## Continuing later

This demo is meant to grow across the day. Once built, use
`/add-teaching-step $ARGUMENTS` any number of times to add more steps —
each call clarifies and paraphrases the new addition back to you before
touching any file, appends it without disturbing earlier verified steps,
and re-verifies the whole artifact. Don't re-run `/run-teaching-pipeline`
for incremental additions to an existing demo — that's what
`/add-teaching-step` is for.

## On failure

`teaching-debug` handles this automatically as part of `teaching-verify` —
it keeps iterating on genuinely different hypotheses until the artifact
runs, or reports exactly what it tried and what's needed to unblock it if
it's genuinely stuck (e.g. a missing decision only the user can make).
