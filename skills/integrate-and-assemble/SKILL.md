---
name: integrate-and-assemble
description: Use as the second-to-last step of every plan.md, after all component skills (frontend/backend/agent) have run. Stitches the pieces into one working whole — this is the only skill responsible for the seams between components.
---

# Integrate and Assemble

Component skills each own one slice and know nothing about the others. This
skill is the explicit owner of everything between the slices — without it,
mismatches (wrong routes, divergent env var names, conflicting dependency
versions, no single way to start the app) are nobody's job and slip
through.

## When to use

- Always, as step N-1 of every `plan.md`, after frontend/backend/agent
  component skills have finished, before `run-and-verify`.

## Procedure

1. **Contract check**: read `design.md`'s API contract. For every call the
   frontend makes, confirm the backend implements that exact path/method/
   shape. Fix mismatches on whichever side is wrong per the documented
   contract — don't silently change the contract to match whatever was
   built unless you flag the deviation to the user.
2. **Config check**: list every env var referenced across frontend,
   backend, and agent code. Reconcile names (e.g. frontend `.env.local`
   using `NEXT_PUBLIC_API_URL` must match what the backend actually listens
   on). Update the project's `.env.example` with the final, complete list —
   this is the single source of truth going forward.
3. **Dependency check**: confirm `requirements.txt` and `package.json`
   don't have versions that conflict with what was actually imported in
   code. Add anything `pick-requirements` missed.
4. **Single run path**: produce one way to start everything — prefer a
   `Makefile` or `run.sh` at the project root (`make dev` / `./run.sh`)
   that starts backend and frontend together (or a `docker-compose.yml` if
   the brief calls for containerization). Document it in the project
   README as the only way to run, not one of several.
5. Hand off to `run-and-verify` — do not attempt to smoke-test here, that's
   a separate step with its own responsibility.
