<!-- Ported from #r-cloudrun of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook C — Cloud Run + managed state

Main concept: Cloud Run containers are replaceable. Important state must live elsewhere.
Run `common-first-steps.md` before this file.

### Step 1 — Refactor local persistent state out of the container `[AUTO]`
Goal: the app should work even if the container filesystem is deleted.
- **SQLite → Turso, minimal migration:** swap the client library for a libSQL client;
  most existing SQL is unchanged. Fastest fix if Cloud Run's ephemeral filesystem is the
  only reason you're doing this migration.
- **SQLite/checkpoints → Postgres:** Supabase, Neon, Cloud SQL or another Postgres. Use
  Alembic/schema scripts plus pgloader, CSV or Python for data migration.
- **Vectors → pgvector:** simplest when already using Postgres.
- **Vectors → dedicated DB:** use Qdrant/Pinecone/etc. when you need specialized
  features/scale.
- **Files → object storage:** GCS is natural on GCP; S3-compatible stores also work.
- **Cache → managed Redis:** only if it solves a measured need.

**Concrete SQLite → Postgres migration path**
1. Create Postgres and copy connection URL.
2. Make app read `DATABASE_URL`.
3. Install Postgres driver.
4. Create Alembic migrations or schema SQL.
5. Run migrations on empty Postgres.
6. Migrate records with pgloader, CSV or Python.
7. Run real workflows locally against Postgres.
8. Compare row counts and sample data.

**Check:** run the local app with no local state files. Required state should still
exist.

### Step 2 — Create a Dockerfile `[AUTO]`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```
If using Playwright/Chromium, install the browser and system dependencies in the image.

### Step 3 — Test Docker locally `[AUTO]`
```bash
docker build -t agent-app .
docker run --env-file .env -p 8080:8080 agent-app
```
Do not continue until Docker works locally.

### Step 4 — Create GCP project and billing guardrails `[HUMAN]`
> In the GCP console: create/select a project, enable billing, create a budget alert,
> enable the Cloud Run/build/registry/secret APIs, and use a conservative maximum
> instance count while learning. Confirm once done.

### Step 5 — Put secrets in Secret Manager `[HUMAN]`
> Add secrets via the GCP console (easiest for the first deploy) or gcloud/IaC (better
> once setup needs to be repeatable). Grant the runtime service identity only the
> permissions it needs. Confirm when done — never paste secret values into this chat.

### Step 6 — Build and deploy `[AUTO]` propose a default, state it / `[HUMAN]` for the deploy trigger
- **Deploy from source:** simplest first path.
- **GitHub Actions:** build/push/deploy automatically after tests.
Propose deploy-from-source for the first deploy, state the reasoning in one line, proceed
unless the user objects. Configure region, memory, CPU, timeout, concurrency, max
instances and minimum instances only when required.
`[HUMAN]`: running the actual `gcloud run deploy` (or approving the GitHub Actions run)
touches billing — confirm before it fires.

### Step 7 — Choose long-run execution pattern `[AUTO]` propose a default, state it
- **Short/medium:** run directly in request if comfortably inside timeout.
- **Long:** API creates job → queue → worker/Cloud Run Job executes → DB stores
  progress/result.
- **Human approval:** persist checkpoint and stop compute; later event resumes run.
Propose based on the profile's `duration`/`hitl` fields, state the reasoning in one line,
proceed unless the user objects.

### Step 8 — Wire UI and authentication `[AUTO]` propose a default, state it
- **Same container:** simplest.
- **Separate frontend:** configure API URL, CORS, auth token flow and streaming.
Propose based on the profile's `uiType`, state the reasoning in one line, proceed unless
the user objects.

### Step 9 — Add CI/CD and rollback `[AUTO]`
PR → tests/evals → build → new Cloud Run revision → smoke test. Roll back by routing
traffic to a previous revision.
