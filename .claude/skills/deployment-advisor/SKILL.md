---
name: deployment-advisor
description: Use any time after a project/concept/teaching demo has passed run-and-verify/teaching-verify, when the user wants to know how/where to deploy it. Studies the project's actual architecture and recommends Vercel-only, Vercel + GitHub Actions, or Vercel + Render/Railway, with a step-by-step manual walkthrough. Read-only — generates no config files and takes no deployment action.
---

# Deployment Advisor

Advisory-only. This skill's entire job is to study a project and tell the
user how they'd deploy it and why — it never writes a Dockerfile,
`vercel.json`, `render.yaml`, or any other config, and never runs a
deployment command. If the user wants those files generated after reading
the recommendation, hand off to `deploy-config` (platform config) and/or
`containerize-project` (Docker/Compose/Makefile) — this skill's output is
the plan those act on, not a replacement for them.

## When to use

- The user asks "how would I deploy this," "what do I need to go live,"
  or similar, for an already-built `projects/`/`concepts/`/`teaching/`
  unit — any time after it has a working local run path
  (`run-and-verify`/`teaching-verify` passed at least once). If it doesn't
  run locally yet, say so and stop — a deployment plan for code that
  doesn't run yet is guesswork.

## Procedure

### 1. Study the project — don't guess the architecture

Read the project's `README.md`, `design.md`/`teaching_brief.md`, and the
actual folder structure. Determine, concretely:
- **Frontend**: Next.js, Streamlit, or none. This matters a lot —
  Streamlit is a persistent Python server, not a static/serverless
  frontend, so a Streamlit app is never "Vercel-only" regardless of
  backend simplicity; it needs a real host (Render/Railway/Streamlit
  Community Cloud) or a container.
- **Backend**: none (frontend calls the LLM provider directly), FastAPI,
  or an agent/graph module with its own process needs.
- **Statefulness**: does any component hold in-memory state across
  requests (a local vector index like FAISS/ChromaDB loaded into memory,
  LangGraph checkpointing to local disk/sqlite, an in-process cache)? This
  is incompatible with stateless serverless functions.
- **Long-lived connections**: streaming responses beyond a few seconds,
  websockets, or server-sent events held open — serverless functions
  (Vercel included) have execution time limits this can exceed.
- **Background/scheduled work**: ingestion pipelines, cron jobs, queue
  workers — anything that isn't triggered by an incoming HTTP request.
- **External managed dependencies**: Qdrant Cloud, a hosted DB, etc. —
  these are reachable from anywhere and don't themselves dictate the
  compute platform, unlike a *local* vector store.
- **CI needs**: does the project have a test suite (`run-tests` output),
  lint/typecheck gates, or an eval suite (`eval-and-observability`) that
  should run automatically on every push, independent of where it's
  hosted?

### 2. Classify against the three tiers

Use this as a decision guide, not a rigid lookup — state the specific
factors from step 1 that drove the classification, don't just name the
tier.

**Vercel-only** — all of:
- Frontend is Next.js (or no frontend beyond API routes).
- No local/stateful vector store — either no retrieval, or it's on a
  managed external service reachable over HTTPS.
- No long-lived connections beyond what Vercel's streaming/edge functions
  support, no websockets.
- No background/scheduled work beyond what Vercel Cron covers.
- Backend logic (if any) is expressible as Next.js API routes / Vercel
  serverless functions — no separate always-on process needed.

**Vercel + GitHub Actions** — Vercel-only's architecture, plus a real need
for CI automation independent of the deploy itself:
- A test/lint/eval suite that must gate merges or run on a schedule.
- Multi-step or multi-environment deploy orchestration (e.g., run tests,
  then deploy staging, then require approval before production) beyond
  what Vercel's own Git integration does alone.
- GitHub Actions here is for **automation around** the deploy, not for
  hosting compute — the app itself still fits on Vercel.

**Vercel + Render/Railway** (or Render/Railway alone, if there's no
separate frontend) — any one of:
- A Streamlit frontend (needs a persistent host, period).
- A local/stateful vector store (ChromaDB/FAISS) that needs to persist on
  disk and stay resident in memory across requests.
- Long-lived streaming/websocket connections exceeding serverless time
  limits.
- Background workers or scheduled ingestion jobs that need an always-on
  process, not just a cron-triggered function.
- Heavier runtime/memory requirements than a serverless function budget
  (e.g., a locally-loaded embedding model).
- If there's no Next.js frontend at all (e.g., pure FastAPI + Streamlit),
  Vercel may not be in the picture at all — say so plainly rather than
  forcing a Vercel component that doesn't fit.

### 3. Write the recommendation — reasoning first, then the walkthrough

Present, in this order:
1. **The tier**, in one sentence, with the specific factors from step 1
   that drove it (not a generic justification).
2. **What stays on each platform** — e.g. "Next.js frontend -> Vercel;
   FastAPI backend + ChromaDB -> Render, as a single web service."
3. **Step-by-step manual walkthrough** to actually get it live. Concrete
   and platform-specific, e.g. for a Vercel + Render pairing:
   - Push the repo to GitHub (if not already).
   - Render: create a new Web Service, point it at the repo/subfolder,
     set build command (`pip install -r requirements.txt`) and start
     command (matching the project's actual verified run command — don't
     invent one), add every env var from `.env.example`, note the
     assigned `*.onrender.com` URL.
   - Vercel: import the repo, set the root directory to the frontend
     folder if it's a subfolder, add `NEXT_PUBLIC_API_URL` (or whatever
     the frontend's actual env var is) pointing at the Render URL from the
     previous step, deploy.
   - If GitHub Actions is in the mix: add `.github/workflows/ci.yml`
     running the project's actual test command on every push/PR, gating
     merges — describe what it should run, don't write the file (that's
     the user's call whether they want it generated, and out of scope for
     this skill).
   - Verify: hit the deployed frontend, confirm a real request reaches
     the deployed backend and gets a real LLM response — same
     "prove it, don't assume it" discipline as `run-and-verify`, just
     against the live URLs instead of localhost.
4. **What this skill did not do**: no config files were created, nothing
   was deployed. If the user wants to proceed, name the next skill
   explicitly — `deploy-config` for `vercel.json`/`render.yaml`,
   `containerize-project` if a Dockerfile/Compose/Makefile fits the
   chosen platform instead (Render and Railway both accept a Dockerfile
   as their build path, which is often simpler than a buildpack for a
   Python backend with system-level dependencies).

### 4. Record it (optional, still just documentation)

If the user wants it kept, write the recommendation to
`<slug>/DEPLOYMENT_PLAN.md` (tier, reasoning, walkthrough) — this is
still just a document, not a config file, and not itself a deployment
action.
