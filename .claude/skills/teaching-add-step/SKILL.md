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
  artifact — a notebook/script, or a `full_app` (Streamlit + FastAPI) demo
  — and the user wants to add another step or feature on top of it, at any
  point during the day, any number of times. Works the same regardless of
  which format the demo already is.

## Procedure

1. **Load context first.** Read the existing `teaching_brief.md` (its full
   step log and `Format` field, not just the latest entry) and the current
   artifact. Know what already exists before proposing anything — never
   re-derive from scratch or assume you remember correctly from earlier in
   the conversation if this is a new session.
2. **Get the feature description.** The user describes the new feature in
   plain language — freeform, any level of detail (e.g. "add a step that
   lets the user upload a CSV and ask questions about it via the same
   agent"). If it wasn't already supplied when this skill was invoked, ask
   for it now, open-ended — don't assume a format or scope in advance.
3. **Clarify only genuine gaps.** Same discipline as `write-project-brief`'s
   freeform-description handling: note what the description already
   answers, and ask only about what's genuinely missing or ambiguous — how
   it should behave, whether it replaces or extends existing
   functionality, any new dependency/env var it needs. Don't guess at
   scope, and don't re-ask what was already stated.
4. **Paraphrase back and get explicit approval before building — mandatory,
   every time.** State in plain language what you're about to add and how
   it fits onto what already exists, e.g.: "So this adds conversation
   memory on top of the tool-calling agent from step (c) — the agent will
   remember prior turns in the same session and can still call tools.
   Sound right?" **Wait for the user's explicit yes before touching any
   file** — this is the one mandatory checkpoint in this lightweight
   track, same role as the test-confirmation gate in the full pipeline.
5. Only after approval, append a new lettered/numbered entry to
   `teaching_brief.md`'s step log (don't rewrite prior entries) with a
   short "Added <date/session>" note.
6. Hand off to `teaching-build` in **append mode**, branching on the
   brief's `Format`:
   - `notebook`/script: add new cells/code on top of the existing
     artifact, reusing whatever setup (LLM client config, prior helper
     functions) earlier steps already established.
   - `full_app`: add the new route(s) to `backend/` and the corresponding
     UI element(s) to `frontend/app.py`, reusing existing config/vector-
     store/observability wiring rather than recreating it.
   Either way: don't recreate what's already there, and don't modify
   earlier cells/routes unless the new step genuinely requires changing
   something upstream (if so, say so explicitly before doing it, since it
   affects previously verified functionality).
7. Hand off to `teaching-verify` to confirm **both old and new
   functionality work together** — the whole artifact top to bottom for
   notebook/script, or the original happy-path scenario plus the new
   feature's flow for `full_app` — never just the new piece in isolation,
   since an addition can break something that already worked. If anything
   fails, `teaching-verify` invokes the matching debug skill
   (`teaching-debug` for notebook/script, `project-debug` for `full_app`)
   automatically.
8. Report back: confirm old and new functionality both work, and give the
   exact command(s) to run the demo right now.
