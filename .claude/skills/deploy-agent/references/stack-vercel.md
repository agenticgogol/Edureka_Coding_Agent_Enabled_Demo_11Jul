<!-- Ported from #r-vercel of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook D — Vercel frontend + separate agent API

Use this because the frontend needs it. The Python agent usually belongs in a separate
backend. Run `common-first-steps.md` before this file.

### Step 1 — Split frontend and backend `[AUTO]`
```
repo/
  frontend/
  backend/
  .github/workflows/
```
Frontend calls a documented API; it should not import backend internals.

### Step 2 — Define backend API `[AUTO]` propose a default, state it
- **Synchronous:** `POST /api/v1/chat`.
- **Durable async:** `POST /runs` creates run; `GET /runs/{id}` returns status; separate
  event/stream endpoint reports progress.
Propose based on the profile's `duration`/`hitl` fields, state the reasoning in one line,
proceed unless the user objects.

### Step 3 — Deploy backend first `[HUMAN]`/`[AUTO]` mixed — see the matching runbook
Use Managed PaaS (`stack-paas.md`), Cloud Run (`stack-cloudrun.md`) or hyperscaler
(`stack-managed.md`). Complete DB, secrets, workers and tracing there first.

### Step 4 — Write `vercel.json` `[AUTO]`
Generate `frontend/vercel.json` from the profile before touching the dashboard:
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "rewrites": [
    { "source": "/api/:path*", "destination": "${BACKEND_BASE_URL}/api/:path*" }
  ]
}
```
Include the `rewrites` block only if Step 6 below chooses the proxy approach; omit it if
the app will use CORS directly. Swap `buildCommand`/`outputDirectory` for the actual
framework in use (this example assumes Next.js). Commit the file — Vercel reads it
automatically on import, which is what Step 5 relies on.

### Step 5 — Deploy frontend `[HUMAN]`
> In Vercel: import the GitHub repo, select `frontend` as the project root, set
> framework/build settings, and add the backend base URL as an environment variable.
> Confirm once deployed.

### Step 6 — Implement authentication end-to-end `[AUTO]`
Browser logs in → token/session → frontend calls backend → backend verifies token and
derives user/tenant identity.
Do not trust a browser-provided `user_id` or `tenant_id` without server-side
authorization.

### Step 7 — Configure CORS or same-origin proxy `[AUTO]` propose a default, state it
- **CORS:** backend explicitly allows production frontend origin.
- **Proxy:** frontend routes `/api/*` to backend, which can simplify browser origin
  handling.
Propose based on architecture simplicity for this profile, state the reasoning in one
line, proceed unless the user objects.

### Step 8 — Test streaming in production `[HUMAN]`
> Verify SSE/WebSocket through the real deployed path — local success is not enough.
> Confirm what you see in the deployed app.

### Step 9 — Separate staging and production `[AUTO]`
Preview deployments should call staging backend/data by default.

### Step 10 — Rollback independently `[AUTO]`
Keep API contracts backward compatible so frontend/backend can be rolled back
separately.
