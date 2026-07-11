# _shared/

Reference templates that every project/concept's `helper-utils` step copies
from, instead of reinventing config loading and LLM provider switching
from scratch each time. This is what keeps env var names and required-key
behavior consistent across projects (see `integrate-and-assemble`).

**No mock mode anywhere in this repo.** `config.py` raises
`MissingAPIKeyError` immediately at import time if no provider key is set.
`llm_client.py` never returns a canned/placeholder response — every call
goes to a real provider or raises. The `require-api-key` skill is the gate
that checks and verifies a working key *before* any of this code is even
written, so hitting this error during a build means something regressed.

**This is a copy-from source, not a shared runtime import.** Each project
must stay independently runnable and deployable (no cross-project import
path), so `helper-utils` copies `config.py` and `llm_client.py` into the
project and adapts as needed — it does not `import` from `_shared/`
directly at runtime.

## Files

- `config.py` — env loading + typed access + `require_llm_key()`, which
  raises immediately if no provider key is configured.
- `llm_client.py` — provider-swappable LLM client (Anthropic / OpenAI /
  Groq) plus `verify_key()`, a cheap real call used to confirm a
  configured key actually works before a build starts.

## Convention

- Any project needing config/LLM access: `helper-utils` copies these two
  files into `backend/` (or the concept root), then edits only what the
  project's `design.md` requires (e.g. added env vars) — the required-key
  / provider-switch pattern should not be reinvented per project.
- If a project's needs genuinely don't fit this pattern, that's a signal to
  update `_shared/` itself (so the next project benefits too), not to fork
  silently. Flag it and update this README's file list when you do.
