---
name: setup-venv
description: Use when a plan.md step calls for Python environment setup. Creates and documents a virtual environment for a project/concept folder.
---

# Setup Venv

## When to use

- First build step for any project/concept with Python code (backend,
  agent, or notebook).

## Procedure

1. Default to stdlib `venv` for simplicity unless the brief/design
   specifies `uv` or `poetry`:

```bash
cd projects/<slug>  # or concepts/<slug>
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

2. If `pick-requirements` has already produced `requirements.txt`, install
   it now; otherwise this step runs before that one — just create the env.
3. Add a one-line "Setup" section to the project/concept `README.md`
   documenting the exact activation command, so `run-and-verify` and future
   readers don't have to guess.
4. Never install into the global/system Python. Never reuse a venv across
   projects — each project/concept is independently runnable.
