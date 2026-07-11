---
name: teaching-build
description: Use after teaching_brief.md is approved. Builds the progressive notebook/script one step at a time, each step visibly adding to the previous, runnable and shown before moving to the next.
---

# Teaching Build

Builds `teaching/<slug>/teaching_brief.md`'s ordered steps as one
progressively-growing artifact — not separate isolated files per step.
The point is that a student watching sees step (b)'s code as step (a)'s
code plus one clear addition, not a fresh unrelated example.

## When to use

- **Initial build**: after `teaching_brief.md` is approved, in place of the
  full `write-and-validate-tests` → `make-plan` → component-skill chain
  used for `projects/`/`concepts/`. This skill alone does the building.
- **Append mode**: called by `teaching-add-step` after it has paraphrased
  and confirmed a new step with the user. In this mode, only build the new
  step(s) — do not regenerate or rewrite cells/code for steps that already
  exist and were already verified, unless the new step genuinely requires
  changing something upstream (and if so, flag that explicitly before
  doing it).

## Procedure

1. For **notebook** format: create `teaching/<slug>/notebook.ipynb`. For
   each step in order:
   - One markdown cell: what this step adds and why, 2-4 sentences.
   - One code cell: the previous step's code plus this step's addition,
     clearly delineated (a short comment marking what's new is fine, but
     don't over-comment). Each cell must be runnable on its own once
     prior cells have executed — a student stepping through top-to-bottom
     always has working code at every point, not just at the end.
   - One short cell or printed output showing the step actually working
     (e.g. print the response, print the tool call trace, print retrieved
     chunks).
   - Skip formal "Exercise"/"Challenge task" sections unless the user asks
     for them — this is a demo sequence, not the certification-grade
     notebook contract from `notebook-concept`.
2. For **script/small project** format: create `teaching/<slug>/app.py`
   (or `teaching/<slug>/steps/step_a_*.py`, `step_b_*.py`, ... if the user
   wants each step individually runnable and diffable) — same principle,
   each step's file is the previous plus one addition.
3. Route any LLM calls through a minimal inline provider-swap (reuse
   `_shared/llm_client.py`/`config.py` via `helper-utils` if the sequence
   is non-trivial enough to warrant it — for a 5-step demo like "API call
   → system prompt → tool call → memory → basic RAG," it's worth it since
   step (a)'s client setup is reused by every later step).
4. No mock mode — every step calls a real provider. `require-api-key` must
   have already verified a working key before `teaching-build` runs (this
   is checked once per demo, not per step); build cells assuming that key
   is live, and let a genuine failure surface as a real error for
   `teaching-debug` to handle, not a silent mock fallback.
5. For the RAG-type step specifically (or any step needing sample data):
   use small local synthetic/sample files under `teaching/<slug>/data/` —
   don't require the user to supply a real PDF before the demo runs once.
6. When done, all steps live in one artifact a student can run top to
   bottom and see the concept build up live.
