---
name: lint-and-typecheck
description: Use after all component code is built (frontend/backend/agent), before integrate-and-assemble. Runs static checks — lint + type check — so type errors and style issues are caught before the runtime smoke test, not by it.
---

# Lint and Typecheck

`run-and-verify` is a runtime smoke test — it only proves the one path it
exercises works. It won't catch a type error in a branch that test didn't
hit, or a lint issue that's a real bug (unused variable that should have
been used, unreachable code). This skill is the static-analysis gate that
runs before that.

## When to use

- Always, after component-building skills finish, before
  `integrate-and-assemble`. Add it to `plan.md` as its own step.

## Procedure

1. **Python** (backend/agent):
   - Type check: `mypy .` (or `pyright` if the project prefers it) against
     `backend/` — fix reported errors; don't add `# type: ignore` to
     silence something actually wrong.
   - Lint: `ruff check .` (fast, covers common bugs + style) — fix
     reported issues.
2. **TypeScript/Next.js** (frontend):
   - Type check: `tsc --noEmit`.
   - Lint: `next lint` (or `eslint .` if configured).
3. Add both commands to `pick-requirements`' dependency list
   (`mypy`/`ruff` for Python dev deps, already bundled with `next lint` for
   Next.js) if not already present.
4. Fix every reported issue before moving on — do not proceed to
   `integrate-and-assemble` with known type/lint errors. If a check can't
   pass for a legitimate reason (e.g. a third-party stub is missing),
   document why in the project README rather than silently suppressing it.
5. Record the exact commands run in the project README's "Development"
   section so a human can re-run them later.
