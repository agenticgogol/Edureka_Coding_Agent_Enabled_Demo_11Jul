---
name: frontend-nextjs
description: Use when plan.md calls for a Next.js frontend. Scaffolds frontend/ per this repo's conventions, calling the backend contract defined in design.md — no backend or agent logic here.
---

# Frontend (Next.js)

## When to use

- Default frontend choice for `projects/` unless the brief explicitly asks
  for Streamlit or another framework (see `frontend-streamlit`).

## Procedure

1. Scaffold under `projects/<slug>/frontend/` using the App Router
   (`app/` directory), TypeScript, minimal dependencies — no UI kit unless
   the brief needs one; plain CSS or Tailwind is enough for a demo.
2. Read the "API contract" section of `design.md` — every fetch call in the
   frontend must match a documented endpoint exactly (method, path, request/
   response shape). Do not invent endpoints; if one is missing, flag it back
   to `technical-design` instead of guessing the backend's behavior.
3. Read env vars from `design.md`'s "Environment variables" section via
   `NEXT_PUBLIC_*` for anything the browser needs, non-prefixed for
   server-only values. Never hardcode a backend URL — use an env var with a
   sensible local default (`http://localhost:8000`).
4. Include a minimal `package.json` with a `dev` script and a `README`
   snippet on how to run (`npm install && npm run dev`).
5. This skill does not touch `backend/` or agent code, and does not attempt
   to run/verify the full stack — that's `integrate-and-assemble` and
   `run-and-verify`.
