---
name: frontend-streamlit
description: Use when plan.md/design.md calls for a Streamlit UI instead of Next.js — typically for concepts/ demos or simple internal-tool-style projects. Scaffolds a single app.py UI.
---

# Frontend (Streamlit)

## When to use

- `concepts/` demos that need a UI beyond a notebook.
- `projects/` where the brief explicitly prefers a fast, Python-only UI over
  Next.js (e.g. an internal tool, not a customer-facing app).

## Procedure

1. Scaffold a single `frontend/app.py` (or `app.py` at the concept root for
   simple concepts) using Streamlit.
2. Same rule as `frontend-nextjs`: every call into the backend/agent must
   match `design.md`'s API contract or direct function import — don't
   invent behavior.
3. Read config from environment variables via the `helper-utils` config
   loader, not hardcoded values. No mock mode — the app requires the
   provider key `require-api-key` already verified; if it's ever unset,
   `config.py` fails immediately with a clear message rather than the app
   silently running degraded.
4. Add `requirements.txt` entry for `streamlit` (deferred to
   `pick-requirements` if that step hasn't run yet — flag it, don't skip
   pinning).
5. Include a `README` run snippet: `streamlit run app.py`.
