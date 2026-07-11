---
name: validate-env
description: Use after helper-utils sets up config.py and before run-and-verify. Confirms every env var the code actually reads is documented in .env.example, and that required vars actually fail loudly (not silently) if unset.
---

# Validate Env

Env var drift — code reading a variable that isn't in `.env.example`, or
`.env.example` listing something nothing reads — is a common source of "it
works on my machine" bugs and confusing setup instructions. This skill
closes that loop mechanically.

## When to use

- After `helper-utils` (config.py is copied/adapted) and after
  component-building skills finish, before `run-and-verify`.
- Re-run any time a new env var is introduced during integration fixes.

## Procedure

1. Grep the project's code (`backend/`, `frontend/`, agent modules) for
   every place an environment variable is read (`os.environ`,
   `process.env`, the project's `config.py`/`Config` class fields).
2. Compare that list against the project's own `.env.example` (create one
   at the project root if it doesn't exist yet, seeded from the repo-root
   `.env.example` plus anything project-specific from `design.md`'s
   "Environment variables" section).
3. Fix mismatches both ways:
   - A var the code reads but `.env.example` doesn't list -> add it, with a
     one-line comment on what it's for and whether it's required or
     optional.
   - A var in `.env.example` that nothing reads -> remove it, or if it's
     forward-looking, flag it rather than leaving dead config.
4. Confirm every var is clearly marked required or optional, and that a
   missing **required** var (at minimum, the LLM provider key) causes an
   immediate, clear error at startup — never a silent no-op or a degraded
   path. There is no mock mode in this repo; if a var is required, its
   absence must stop execution with a message telling the user what to
   set, not run anyway with reduced functionality.
5. **Run the actual check**: temporarily rename/unset `.env` (or run in a
   clean shell with none of the vars exported) and confirm the project
   **fails immediately with a clear "set X" message**, not a confusing
   downstream error or silent degraded behavior. This is the negative-path
   test that matters here — the positive path (`require-api-key` already
   verified the key works) is confirmed separately.
