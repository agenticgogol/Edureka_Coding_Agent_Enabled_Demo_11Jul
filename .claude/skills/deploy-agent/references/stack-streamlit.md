<!-- Ported from #r-streamlit of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook A — Streamlit / Gradio managed hosting

Best for a novice: quickest route to a working URL when the app can tolerate limited
infrastructure control. Run `common-first-steps.md` before this file.

### Step 1 — Make the app host-friendly `[AUTO]`
Use relative paths, environment variables and an obvious entry file such as `app.py`. If
you require Chromium, ffmpeg or OCR binaries, verify the host supports them; otherwise
choose container/PaaS/VM.

### Step 2 — Move durable state off the app filesystem `[AUTO]`
Goal: a restart must not erase memory, RAG data or user files.
- **Relational/checkpoint options:** Turso is usually the least-migration path — it's
  SQLite-compatible, so most existing queries work with only a client-library swap, not a
  rewrite. Supabase/Neon Postgres are the alternative if you're willing to move to
  Postgres syntax (needed if you want pgvector in the same database). See
  `provider-picks.md`.
- **Vector options:** pgvector for simplest architecture; Qdrant/Pinecone/another vector
  DB when you want a specialized vector service.
- **File options:** S3, R2, GCS, Azure Blob or Supabase Storage.

**Example: migrate SQLite to Supabase/Neon/Postgres**
1. Create the hosted Postgres database and copy its connection string.
2. Change app config from a local SQLite path to `DATABASE_URL`.
3. If using SQLAlchemy, install a Postgres driver and add Alembic migrations.
4. Create tables by running the migration scripts.
5. Move existing data using pgloader, CSV export/import, or a Python migration script.
6. Compare row counts and manually inspect sample records.
7. Run the app locally against Postgres before deploying.

**Check:** delete local DB/state files, restart locally, and confirm required old data
still exists remotely.

### Step 3 — Connect GitHub to the host `[HUMAN]`
> Choose repository → branch `main` → entry file in the host's UI. The host should
> install dependencies and launch the process. Confirm the connection is set up before I
> continue.

### Step 4 — Add secrets in the host UI `[HUMAN]`
> Copy values from your local `.env` into the provider's secret settings. Never paste
> secrets into source code, or into this chat. Confirm when done.

### Step 5 — Protect access `[AUTO]` propose a default, state it
- Built-in sharing/auth: simplest if adequate.
- External auth: Supabase/Auth0/Clerk/etc. if supported.
- Enterprise SSO/private network: move to managed PaaS or hyperscaler rather than forcing
  a demo host.
Propose the option matching the profile's `authMode` and state the reasoning in one line;
proceed unless the user objects.

### Step 6 — Smoke test like a brand-new user `[HUMAN]`
> Open the deployed URL in incognito mode. Test login, one agent run, tool call, RAG
> retrieval, file upload, error path and persistence after a restart/sleep. Tell me what
> you see.

### Step 7 — Add tracing and basic alerts `[AUTO]`
Capture exceptions and agent traces. At minimum, you should be able to answer: which run
failed, at which model/tool step, and why?
