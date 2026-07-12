---
name: containerize-project
description: Use any time after a project/concept/teaching demo has passed run-and-verify/teaching-verify, when the user wants a Dockerfile, docker-compose.yml, and/or Makefile for it. Studies the actual project folder to detect its stack, checks that Docker/Compose/Make prerequisites are actually installed, and only generates files after the user has resolved anything missing.
---

# Containerize Project

Standalone, user-invoked skill — not part of any pipeline's default stage
list. A project/concept/teaching demo is expected to already run locally
(via `run-and-verify` or `teaching-verify`) before this skill is called;
this skill packages that already-working thing for Docker/Make, it does
not fix a broken build.

Distinct from `deploy-config`: `deploy-config` targets a specific hosting
platform (Vercel/Render) and is brief-gated as part of the pipeline. This
skill targets local/portable containerization (Docker + Compose + Make)
and is called on demand, any time, independent of any pipeline run. If
`deploy-config`'s brief calls for containerization instead of a hosting
platform, it should invoke this skill rather than generating its own
Dockerfile/compose file, to avoid two places doing the same job.

## When to use

- The user explicitly asks for a Dockerfile / docker-compose.yml /
  Makefile for an existing `projects/`, `concepts/`, or `teaching/` unit.
- Only after that unit has a working local run path — check its README's
  "how to run" / "Testing" section (or ask, if it's missing) before
  starting. If it doesn't run locally yet, say so and stop; containerizing
  something that doesn't work yet just reproduces the failure in Docker.

## Procedure

### 1. Study the project folder first — don't assume a stack

Read, in order: the project's `README.md` (run command, provider/model,
vector store, observability setup), `design.md`/`teaching_brief.md` if
present (architecture, ports, env vars), and the actual folder structure
(`backend/`, `frontend/`, `notebook.ipynb`, `app.py`, `requirements.txt`,
`package.json`, `.env.example`). Determine:
- How many independently-runnable services actually exist (e.g. FastAPI
  backend + Streamlit frontend = 2 services; a single `app.py` = 1; a
  notebook = usually not a service at all — ask whether the user wants a
  reproducible-environment image for it or is really asking about a
  `full_app`-format sibling instead).
- The exact run command each service currently uses locally (from the
  README) — the containerized command must match, not invent a different
  one.
- Every env var each service reads (from `.env.example` — this is the
  authoritative list per `validate-env`/`helper-utils`).
- Any external dependency that isn't itself containerizable from here
  (e.g. Qdrant Cloud — a managed service, not something `docker-compose`
  spins up locally; ChromaDB/FAISS are local and do belong in the compose
  file or the image itself).

### 2. Check prerequisites — before generating anything

Do not write any file until this step passes or the user has explicitly
told you to proceed anyway.

1. Check Docker is installed and the daemon is actually running:
   `docker version` (not just `docker --version` — that only proves the
   CLI binary exists, not that the daemon is reachable).
2. If a `docker-compose.yml` is in scope: check Compose is available —
   `docker compose version` (Compose v2 plugin) or `docker-compose
   --version` (standalone v1) — note which one is present, since the
   generated run instructions must use the right invocation.
3. If a `Makefile` is in scope: check `make --version` is available.
4. **Report exactly what's missing, with the real install step for the
   user's OS if it can be inferred (or ask), and stop.** Do not generate
   Dockerfile/compose/Makefile content yet if a required tool is missing —
   ask the user to install/start it, then re-check before proceeding. This
   mirrors `require-api-key`'s hard-stop discipline: a prerequisite that
   isn't actually verified is not a prerequisite that's met.
5. Once every required tool for what's being generated is confirmed
   present (and, for Docker, the daemon responds), tell the user what
   passed and proceed.

### 3. Generate only what the user asked for

Ask first if the user didn't specify which of the three they want — don't
generate all three by default if they only asked for "a Dockerfile."

**Dockerfile** (one per service, or one multi-stage file if the project is
single-service):
- Base image matching the project's actual runtime (e.g.
  `python:3.11-slim` for FastAPI/Streamlit backends, matching whatever
  Python version `pick-requirements`/`setup-venv` targeted).
- Multi-stage only if it earns its complexity (e.g. a Next.js frontend
  with a build step) — don't multi-stage a simple single-file Streamlit
  app.
- Copy only `requirements.txt`/`package.json` first, install, then copy
  the rest — standard layer-caching order.
- Run as a non-root user.
- `EXPOSE` the actual port the service listens on (from the README/design,
  not a guessed default).
- `CMD`/`ENTRYPOINT` matching the exact locally-verified run command
  (e.g. `uvicorn backend.main:app --host 0.0.0.0 --port 8000`).
- No secrets baked into the image — env vars are supplied at `docker run`/
  compose time, never hardcoded, never `COPY .env`.

**docker-compose.yml** (when there's more than one service, or the user
wants Docker-based local dev even for one):
- One service per component detected in step 1, plus a service for any
  *locally-hostable* vector store the project uses (e.g. ChromaDB) — never
  add a compose service for a cloud-managed dependency like Qdrant Cloud;
  instead note in a comment that it's external and its URL/key come from
  `.env`.
- `env_file: .env` per service rather than inlining vars.
- `depends_on` reflecting real startup order (e.g. frontend depends on
  backend; backend depends on a local vector-store service if any).
- Port mappings matching each Dockerfile's `EXPOSE`.
- A named volume for any local vector store's persistence directory, so
  data survives a `docker compose down` (not `docker compose down -v`).

**Makefile**:
- Targets covering both the plain-local and Docker workflows so the file
  is useful regardless of which the user reaches for: `install` (create
  venv + install deps, matching `setup-venv`/`pick-requirements`), `run`
  (the plain local run command), `test` (matching `run-tests`'s actual
  invocation), `docker-build`, `docker-up`, `docker-down`, `docker-logs`,
  `clean`.
- Use whichever Compose invocation step 2 confirmed is actually installed
  (`docker compose` vs `docker-compose`) — don't hardcode the other one.
- Keep each target a thin wrapper around a real command, not new logic —
  this file should never be the place business logic lives.

### 4. Never silently overwrite existing files

If `Dockerfile`/`docker-compose.yml`/`Makefile` already exist, show the
user what would change and confirm before overwriting — treat existing
versions the same as any other in-progress work per this repo's general
rule against silently discarding things.

### 5. Verify what you generated actually builds

Once files are written and prerequisites are confirmed present, run a real
`docker build` (or `docker compose build`) — not just `docker compose
config` for syntax — to catch dependency-resolution or Dockerfile errors
before handing this back as done. If the build fails, fix it and rebuild;
don't hand back an unverified Dockerfile as "should work." Actually
starting the container(s) (`docker compose up`) and hitting the running
service is a good final check but is the user's call whether to do now —
tell them the exact command either way.

### 6. Report

Summarize: which files were created/updated, which prerequisites were
confirmed, the exact commands to build and run (both `make` targets and
the raw `docker`/`docker compose` commands), and any external dependency
(e.g. Qdrant Cloud credentials) the user still needs to have in `.env`
before `docker compose up` will fully work.
