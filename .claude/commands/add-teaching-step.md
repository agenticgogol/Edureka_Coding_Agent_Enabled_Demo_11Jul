---
description: Add a new step/feature to an EXISTING teaching demo (continue building on a notebook/project you started earlier today). Clarifies, paraphrases, appends, then verifies the whole thing again.
argument-hint: <teaching-slug>
---

`$ARGUMENTS` is an existing teaching demo slug under `teaching/`. Use this
any time during the day to keep extending it — the teaching track is meant
to be a living artifact, not a one-shot build.

## Preconditions

- `teaching/$ARGUMENTS/teaching_brief.md` must exist. If not, tell the user
  to run `/new-teaching-demo $ARGUMENTS` first — this command is for
  extending an existing demo, not starting one.

## Stages

1. **Load context** — read the existing `teaching_brief.md` (full step
   log) and the current artifact (`notebook.ipynb`/`app.py`/`steps/`), so
   the new step is added with full knowledge of what's already there.
1a. **Confirm API key still works** — if it's been a while since the last
    build/verify, or the user mentions any auth error, re-run
    `require-api-key` before proceeding. No mock mode — a dead key is a
    hard stop, not something to build around.
2. **Clarify and paraphrase** — `teaching-add-step`. Ask enough to pin down
   the new step's scope if the request is vague, then **state back in
   plain language** what will be added and how it builds on existing
   steps. Wait for the user to confirm before touching any file — this is
   the one mandatory checkpoint in this lightweight track.
3. **Append** — `teaching-build` in append mode: add the new step's
   cells/code on top of the existing artifact without disturbing earlier,
   already-verified steps (unless the new step genuinely requires an
   upstream change — flag that explicitly first).
4. **Re-verify the whole thing** — `teaching-verify`, running top to
   bottom (not just the new step), since a new addition can break an
   earlier one. On any failure, `teaching-verify` invokes `teaching-debug`
   automatically — let it iterate until fixed rather than stopping at the
   first error.
5. **Report** — what was added, confirm it runs against the real provider,
   and update `teaching/$ARGUMENTS/README.md` if the run instructions
   changed.

This command can be run as many times as needed across a day — each call
is one more increment on the same living artifact.
