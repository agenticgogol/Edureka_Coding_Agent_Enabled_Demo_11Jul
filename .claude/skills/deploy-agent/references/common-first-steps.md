# Common first steps — run before any stack-specific runbook

Ported from §04 of the HTML guide. These apply regardless of which stack was recommended.

### Step 1 — Confirm the app can be recreated from scratch `[AUTO]`
**Goal:** another machine should be able to run this without hidden local state.
Run in a fresh location: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
(or the project's existing Poetry/uv/pip-tools flow — don't change packaging just for this).
**Check:** the app starts successfully from the fresh environment.

### Step 2 — Create a clear environment-variable contract `[AUTO]`
**Goal:** no secrets or machine-specific settings live in code.
Write `.env.example` listing variable names with empty values (`OPENAI_API_KEY=`,
`DATABASE_URL=`, `VECTOR_DB_URL=`, `APP_ENV=local`, plus anything else the scanner found
being read via `os.environ`/`os.getenv`).
**Pitfall:** if a secret was ever committed to git history, removing it from the current
file isn't enough — it must be rotated. Ask the user if this has ever happened.

### Step 3 — Confirm the durable-state inventory `[AUTO]`
Cross-check the capability scanner's findings (`localstate`, `memory`, `vector`, `blob`)
against a quick look for SQLite files, LangGraph checkpoints, local Chroma/FAISS dirs,
uploads, and generated reports. Mark each as **durable state** (must survive a restart) or
**safe-to-recreate cache**. Show the list to the user for a sanity check, don't just assume.

### Step 4 — Create Git locally `[AUTO]`
Write `.gitignore` first (`.env`, local DB files, virtual envs, caches, uploads), then:
```bash
git init && git add . && git status && git commit -m "Production baseline" && git branch -M main
```

### Step 5 — Create the GitHub repository and push `[HUMAN]`
Even though `gh repo create` could run in a Bash tool, creating a real repo is an external,
named artifact — pause here.
> Create a private GitHub repo for this project (via github.com or `gh repo create <name>
> --private --source=. --remote=origin --push`), then confirm it's created and tell me the
> repo URL, or say "done" if you used the `gh` command yourself.
**Check once confirmed:** the repo shows the code but not `.env` or any secret values.

### Step 6 — Add a health check `[AUTO]`
FastAPI: add `@app.get("/health")` returning `{"status": "ok"}` without invoking the LLM.
Streamlit-only apps: skip for now, rely on platform health behavior until a backend exists.
**Check:** calling the health URL returns HTTP 200 with no model call.

Once all six are done, proceed to the stack-specific runbook.
