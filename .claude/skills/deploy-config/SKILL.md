---
name: deploy-config
description: Use only when project_brief.md or design.md explicitly calls for deployment. Generates vercel.json / render.yaml for a project after run-and-verify has passed locally; delegates to containerize-project for Docker/Compose/Makefile.
---

# Deploy Config

## When to use

- Optional, brief-gated step — do not add deployment config to a project
  that didn't ask for it.
- Only after `run-and-verify` passes locally; don't debug deployment
  configuration for code that doesn't run yet.

## Procedure

1. Frontend (Next.js) -> Vercel: add `vercel.json` only if non-default
   settings are needed (Next.js deploys to Vercel with zero config
   otherwise); document required env vars to set in the Vercel dashboard.
2. Backend (FastAPI) -> Render: add `render.yaml` with build/start commands
   matching exactly what `run-and-verify` used locally — don't invent a
   different start command for prod.
3. If the brief calls for containerization instead of (or in addition to)
   a hosting platform: invoke `containerize-project` for the
   `Dockerfile`/`docker-compose.yml`/`Makefile` rather than generating
   them here — it owns the prerequisite checks (Docker/Compose/Make
   actually installed) and the stack-detection logic; don't duplicate
   that.
4. List every required environment variable/secret that must be set in the
   deployment platform (matching the project's `.env.example` exactly) in
   the project README's "Deploy" section.
5. Do not actually deploy or push to any hosting account from here — this
   skill only produces the config files; deployment itself is a user
   action.
