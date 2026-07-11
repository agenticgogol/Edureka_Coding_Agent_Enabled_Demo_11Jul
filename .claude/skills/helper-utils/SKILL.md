---
name: helper-utils
description: Use when a project/concept needs shared plumbing — config/env loading, logging, required-key enforcement. Keeps this logic in one small module instead of duplicated across frontend/backend/agent code.
---

# Helper Utils

## When to use

- Early in most plans, right after `pick-requirements` and after
  `require-api-key` has already confirmed a working key exists — backend,
  agent, and notebook code all depend on this.

## Procedure

1. **Start from `_shared/`, don't write from scratch.** Copy
   `_shared/config.py` and `_shared/llm_client.py` into `backend/`
   (or `<slug>/` for concepts), fix the relative import in
   `llm_client.py`, and only then add any project-specific env vars listed
   in `design.md`. This keeps required-key enforcement and
   provider-switching identical across every project — see
   `_shared/README.md`. There is no mock mode: `config.py` raises
   immediately if no provider key is set.
2. Add minimal logging setup (stdlib `logging`, one configured logger) — no
   third-party logging framework unless the brief specifically needs it.
3. Do not put business logic here — this module is plumbing only
   (config, logging, required-key checks). Domain logic belongs in
   `backend-fastapi` / the agent skills / `frontend-*`.
4. Every other skill that reads an API key or config value must import from
   here rather than calling `os.environ` directly — this is what keeps env
   var names consistent for `integrate-and-assemble` and `validate-env` to
   check later.
5. If a project's needs don't fit `_shared/`'s pattern, update `_shared/`
   itself rather than forking silently, so the next project benefits too.
