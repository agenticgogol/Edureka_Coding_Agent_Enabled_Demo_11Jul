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

1. Execute the notebook top to bottom (`jupyter nbconvert --to notebook
   --execute` or equivalent) or run the script/each step file directly,
   against the real provider.
2. Confirm every step's output cell/print actually shows what the
   accompanying markdown/comment claims — not just "no exceptions raised."
3. If the provider key ever fails mid-session (rate limit, expired,
   revoked), treat that as a hard stop, not something to route around:
   report it and re-run `require-api-key` to get a working key before
   continuing. There is no fallback path.
4. If any step fails for a reason other than the key itself, invoke
   `teaching-debug` immediately — don't just report the failure and stop.
   `teaching-debug` iterates on the real error until it's fixed (or
   genuinely blocked, in which case it tells you exactly what's needed).
   Once fixed, re-run the entire artifact top to bottom again, not just
   the previously-failing step, since a fix can affect steps that depend
   on the same code.
5. Record in `teaching/<slug>/README.md`: how to run it (`jupyter
   notebook notebook.ipynb` or `python app.py`), and which provider/model
   it was verified against.
