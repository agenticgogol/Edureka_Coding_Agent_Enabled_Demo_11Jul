---
name: teaching-add-step
description: Use to add a new step/feature to an EXISTING teaching demo (teaching/<slug>/ already has a notebook or project from a prior session). Clarifies and paraphrases the request before touching any file, then appends without disturbing prior steps.
---

# Teaching Add Step

The teaching track is meant to be a living artifact you keep extending
across a day, not a one-shot build. This skill is what `/add-teaching-step`
calls — it's the incremental counterpart to `teaching-brief` +
`teaching-build`, scoped to "add one more thing to what already exists."

## When to use

- `teaching/<slug>/` already has a `teaching_brief.md` and a built
  artifact (`notebook.ipynb`, `app.py`, or `steps/`), and the user wants to
  add another step, feature, or fix on top of it — at any point during the
  day, any number of times.

## Procedure

1. **Load context first.** Read the existing `teaching_brief.md` (its full
   step log, not just the latest entry) and the current artifact. Know
   what already exists before proposing anything — never re-derive from
   scratch or assume you remember correctly from earlier in the
   conversation if this is a new session.
2. **Clarify.** If the user's request for the new step is short or vague
   ("add memory now," "make it use tools"), ask enough to pin down: what
   exactly should be added, how it should behave, and whether it replaces
   or extends the previous step's behavior. Don't guess at scope.
3. **Paraphrase back before building — mandatory, every time.** State in
   plain language what you're about to add and how it fits onto the
   existing steps, e.g.: "So step (f) will add conversation memory on top
   of the tool-calling agent from step (c) — the agent will remember
   prior turns in the same session and can still call tools. Sound
   right?" Wait for confirmation or correction. This is the same
   discipline as the test-confirmation checkpoint in the full pipeline,
   applied here because there's no separate test-review step in this
   lightweight track — this is the one checkpoint it gets.
4. Only after confirmation, append a new lettered/numbered entry to
   `teaching_brief.md`'s step log (don't rewrite prior entries) with a
   short "Added <date/session>" note.
5. Hand off to `teaching-build` in **append mode**: add new cells/code on
   top of the existing artifact, reusing whatever setup (LLM client
   config, prior helper functions) earlier steps already established —
   don't recreate what's already there, and don't modify earlier cells
   unless the new step genuinely requires changing something upstream (if
   so, say so explicitly before doing it, since it affects previously
   verified steps).
6. Hand off to `teaching-verify` to run the whole artifact top to bottom
   again (not just the new step) — a new step can break an earlier one
   (e.g. a changed import, a renamed variable). If anything fails, use
   `teaching-debug`.
