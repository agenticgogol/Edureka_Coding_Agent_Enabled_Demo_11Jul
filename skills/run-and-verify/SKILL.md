---
name: run-and-verify
description: Use as the final step of every plan.md, after integrate-and-assemble. Installs dependencies, launches the project/concept, and drives one real end-to-end request. A project/concept is not done until this passes.
---

# Run and Verify

The only step that proves the thing actually works, as opposed to "the
files exist and look right." Nothing is marked complete before this passes.

## When to use

- Always, as the last step of every `plan.md`.
- Re-run after any fix made in response to a failure here.

## Procedure

1. Follow the single run path `integrate-and-assemble` produced
   (`make dev`, `./run.sh`, `docker-compose up`, or `streamlit run app.py` /
   notebook execution for concepts). Install dependencies fresh in a clean
   venv/node_modules if possible, to catch anything only working because of
   stray local state.
2. Drive one real request through the whole path:
   - Web app: actually call the frontend page or curl the backend endpoint
     the frontend uses, and confirm a real response — not just "server
     started with no errors."
   - Notebook: execute all cells top to bottom and confirm the "Expected
     output" section's claim actually matches what ran.
3. This must run against a real, working provider key (already verified by
   `require-api-key` before build started) — there is no mock mode in this
   repo to fall back on if the key stopped working; if a call fails here
   due to the key, that's a real failure, fix it (re-verify the key, don't
   patch around it).
4. If anything fails, fix it and re-run this skill — don't hand a failing
   verify back as "mostly done."
5. Record the verified run command in the project/concept README so a
   human or future agent can repeat it without re-deriving it.
