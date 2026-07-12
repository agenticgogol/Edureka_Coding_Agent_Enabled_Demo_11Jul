---
name: teaching-verify
description: Use as the last step of the teaching pipeline. Runs every step of the notebook/script top to bottom against the real, verified provider and confirms each one actually works.
---

# Teaching Verify

The lightweight equivalent of `run-and-verify` for the teaching track —
same principle (prove it runs, don't assume it), much less ceremony than
the full project/concept pipeline (no lint, security, or eval gates here
unless the user explicitly asks for them for this demo). No mock mode: a
real, working provider key is required, and `require-api-key` already
verified it before `teaching-build` ran.

## When to use

- Always, as the final step of `/run-teaching-pipeline` and
  `/add-teaching-step`, after `teaching-build`.

## Procedure

1. For `notebook`/script format: execute the notebook top to bottom
   (`jupyter nbconvert --to notebook --execute` or equivalent) or run the
   script/each step file directly, against the real provider. For
   `full_app` format: install fresh, launch via the run command
   `teaching-build` recorded, and drive the exact happy-path test case
   approved in `teaching-brief` step 4 through the real running UI/API
   (not just "server started with no errors").
2. Confirm every step's output cell/print (notebook) or the happy-path
   scenario's actual UI behavior (full_app) matches what was
   claimed/approved — not just "no exceptions raised."
3. If the provider key ever fails mid-session (rate limit, expired,
   revoked), treat that as a hard stop, not something to route around:
   report it and re-run `require-api-key` to get a working key before
   continuing. There is no fallback path. Same treatment for a vector
   store credential (e.g. Qdrant Cloud) if one is in scope.
4. If any step fails for a reason other than a key/credential, invoke the
   debug skill matching this build's format — `teaching-debug` for
   notebook/script, `project-debug` for `full_app` (it already knows how
   to diagnose frontend/backend/contract issues) — immediately, don't just
   report the failure and stop. Once fixed, re-run the entire artifact
   (top to bottom for notebook; the full happy-path flow again for
   full_app) since a fix can affect something that previously passed.
5. Record in `teaching/<slug>/README.md`: how to run it (`jupyter notebook
   notebook.ipynb` / `python app.py` / the full_app run command), and
   which provider/model, vector store, and observability setup it was
   verified against.
