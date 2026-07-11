---
name: notebook-concept
description: Use when building a concepts/<slug>/ demo as a Jupyter notebook. Generates one atomic-concept notebook following this repo's 7-part teaching contract.
---

# Notebook (Atomic Concept)

## When to use

- Default build path for `concepts/`, unless `design.md` calls for a small
  app instead (then use `frontend-streamlit` + `helper-utils`).
- Only after `require-api-key` has confirmed a working provider key — this
  repo has no mock mode, so any notebook using an LLM API requires a real
  key before it's written, not just before it's run.

## Procedure

Every notebook must teach exactly one concept (per `concept_brief.md`) and
include all seven of these sections as separate cells — this is the
CODEX.md notebook contract, and violating it is the #1 quality problem
flagged in this repo's own gap analysis:

1. **Concept explanation** — markdown cell, plain language, tied to the
   brief's "Learning outcome."
2. **Minimal runnable code** — the smallest code that demonstrates the idea.
   Use synthetic/local data for anything that isn't the LLM call itself.
   Any LLM API call uses a real provider via `_shared/llm_client.py` — no
   mock mode; the key was already verified by `require-api-key` before
   this notebook was written.
3. **Visual intuition** — a plot, printed trace, or ASCII diagram that makes
   the concept visible, not just described.
4. **Small exercise** — a concrete task the learner does by editing a cell.
5. **Expected output** — what the exercise should produce, shown explicitly.
6. **Common errors** — 2-3 real mistakes a learner makes here and what the
   error looks like.
7. **Challenge task** — one harder extension, no solution given.

Save as `concepts/<slug>/notebook.ipynb`. Keep cells short — this is a
lesson, not a script; a notebook satisfying only "minimal runnable code"
out of the seven sections is exactly the failure mode this skill exists to
prevent.
