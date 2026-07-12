---
description: Add a new step/feature to an EXISTING teaching demo (notebook or full Streamlit+FastAPI app) by describing it in plain language — continue building on something you started earlier today. Clarifies, gets your approval, appends, then verifies old + new functionality together.
argument-hint: <teaching-slug> [<feature description>]
---

Parse `$ARGUMENTS` as `<slug> [<feature description>]` — the slug is
required; everything after it, if present, is the new feature described in
your own words (freeform, as detailed or as rough as you like — "add a
step that lets the user upload a CSV and ask questions about it via the
same agent" is a complete, valid description). If you omit the
description, the command asks for it as its first stage.

`teaching/<slug>/` is an existing teaching demo under `teaching/`. Use this
any time during the day to keep extending it — the teaching track is meant
to be a living artifact, not a one-shot build, and this works the same way
whether the demo is a notebook/script or a full `Streamlit + FastAPI` app.

## Preconditions

- `teaching/<slug>/teaching_brief.md` must exist. If not, tell the user
  to run `/new-teaching-demo <slug>` then `/run-teaching-pipeline <slug>`
  first — this command is for extending an already-built demo, not
  starting one.

## Stages

1. **Load context** — read the existing `teaching_brief.md` (full step
   log, including its `Format` field) and the current artifact
   (`notebook.ipynb`/`app.py`/`steps/`, or the `backend/`+`frontend/` pair
   for a `full_app` demo), so the new step is added with full knowledge of
   what's already there.
1a. **Confirm API key still works** — if it's been a while since the last
    build/verify, or the user mentions any auth error, re-run
    `require-api-key` before proceeding. No mock mode — a dead key is a
    hard stop, not something to build around.
2. **Get the feature description, then clarify and paraphrase** —
   `teaching-add-step`. If no description was passed as part of
   `$ARGUMENTS`, ask for it now, open-ended. Then ask enough to pin down
   the new step's scope if the request is vague or leaves a genuine gap,
   then **state back in plain language** what will be added and how it
   builds on existing steps/functionality. **Wait for the user's explicit
   approval before touching any file** — this is the one mandatory
   checkpoint in this lightweight track, and code generation does not
   start without it.
3. **Append** — `teaching-build` in append mode: add the new step's
   cells/code (notebook/script) or the new route(s)/UI element(s)
   (`full_app`) on top of the existing artifact without disturbing
   earlier, already-verified functionality — unless the new step
   genuinely requires an upstream change, in which case flag that
   explicitly before doing it.
4. **Re-verify old + new together** — `teaching-verify`, running the whole
   artifact again (top to bottom for notebook/script; the original
   happy-path scenario plus the new feature's flow for `full_app`), never
   just the new piece in isolation, since an addition can break something
   that already worked. On any failure, this invokes the debug skill
   matching the demo's format — `teaching-debug` for notebook/script,
   `project-debug` for `full_app` — automatically; let it iterate until
   fixed rather than stopping at the first error.
5. **Report** — confirm both old and new functionality work, tell the user
   the demo is done, and give the exact command(s) to run it themselves
   right now. Update `teaching/<slug>/README.md` if run instructions
   changed.

This command can be run as many times as needed across a day — each call
is one more increment on the same living artifact.
