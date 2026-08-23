<!-- Ported from #r-paas of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook B — Managed PaaS

Typical novice-friendly production option: connect GitHub, define a web process, attach
managed services, deploy. Run `common-first-steps.md` before this file.

### Step 1 — Choose one-process or web+worker architecture `[AUTO]` propose a default, state it
- **One web process:** good if every run reliably finishes quickly.
- **Web + worker:** better for multi-minute work, retries or approvals. Web accepts job;
  worker executes; DB stores status/result.
Propose the option matching the profile's `duration`/`background` fields, state the
reasoning in one line, proceed unless the user objects.

### Step 2 — Move local state to managed services `[AUTO]`
- **SQLite, minimal migration:** Turso (libSQL) keeps SQLite semantics — swap the client
  library, keep most queries.
- **Postgres:** provider's own DB, Supabase, Neon or cloud-managed Postgres.
- **Migration methods:** Alembic/schema SQL for structure; pgloader, CSV import/export or
  Python script for existing data.
- **Vectors:** pgvector first unless you need a separate vector platform.
- **Files:** object storage rather than web-service filesystem.
See `provider-picks.md` for the named services and their free/hobby/production tiers.

### Step 3 — Define the start command `[AUTO]`
**FastAPI:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```
**Flask:** use Gunicorn, not the dev server.
**Streamlit:**
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT:-8501}
```

### Step 4 — Decide whether Docker is necessary `[AUTO]` propose a default, state it
- **No Docker:** easiest if native Python support is enough.
- **Docker:** choose for browser binaries, OS packages, reproducibility or portability.
Propose based on the profile's `browser`/`codeexec`/`localmcp`/`heavyparse` flags, state
the reasoning in one line, proceed unless the user objects.

### Step 5 — Write `render.yaml` `[AUTO]`
Generate `render.yaml` at the repo root from the profile before touching the dashboard:
```yaml
services:
  - type: web
    name: agent-app
    env: docker            # or "python" if Step 4 chose no-Docker
    plan: starter           # match the confirmed budget tier
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: OPENAI_API_KEY
        sync: false
```
Add a second `type: worker` service block here if Step 1 chose web+worker. Leave secret
values blank (`sync: false`) — Step 6 below is where real values get entered, and they
never belong in this committed file. Commit `render.yaml` — Render's "New Web
Service/App" flow in Step 5 auto-detects it via Blueprint sync.

### Step 6 — Create the PaaS service `[HUMAN]`
> In the PaaS console: choose "New Web Service/App", authorize GitHub and select the
> repo, select branch `main`, set build/start commands, set `/health` as the health check
> path, choose a region near your DB/users. Tell me once it's created.

Relay the provider choice for the confirmed budget tier before this step (fold in
`provider-picks.md`'s compute table):
> Based on your budget tier (**{tier}**), here are the options:
> - **Free** → Render free web service (Docker or native Python, managed Postgres
>   available) — sleeps after 15 min idle, 30–50s cold wake.
> - **Hobby-paid** → Render Starter ($7/mo) / Railway Hobby ($5/mo) / Fly.io
>   (~$8–25/mo) — no sleep, easy Git deploy, no major con at this budget.
> - **Production** → Cloud Run / ECS Fargate / Azure Container Apps with autoscaling,
>   VPC, IAM — real cloud-engineering surface area, budget for it.
>
> Which provider do you want to use, and do you already have an account?

### Step 7 — Add environment variables and secrets `[HUMAN]`
> Add environment variables and secrets in the PaaS console, using separate staging and
> production values — don't rely on your laptop's `.env` being uploaded. Confirm when
> done.

### Step 8 — Add a worker if needed `[AUTO]` propose a default, state it
- **Simple:** DB-backed `jobs` table with queued/running/succeeded/failed and a polling
  worker.
- **Standard queue:** Redis + RQ/Celery.
- **Managed queue:** cloud/PaaS-native queue if available.
Propose based on the Step 1 decision, state the reasoning in one line, proceed unless the
user objects.

### Step 9 — Add authentication and domain `[HUMAN]`
> Set production callback URLs in your auth provider. I'll verify tokens server-side in
> code. Attach a custom domain and managed TLS in the PaaS console — tell me once DNS
> resolves.

### Step 10 — Add logs/traces and release automation `[AUTO]`
Start with platform logs plus agent tracing. Recommended path: PR tests → merge → deploy
staging → smoke test → production deploy.
If using a free tracing tier (e.g. Langfuse Hobby's 50k units/month), remember a *unit*
is every trace, observation and score combined — a multi-step agent burns through the
free allowance far faster than request count alone suggests. Sample successes; trace all
failures. See `provider-picks.md`.

### Step 11 — Practice rollback `[HUMAN]`
> Deploy a harmless change with me, then revert to the previous deploy using the
> provider's deploy history. Confirm durable state is unaffected.
