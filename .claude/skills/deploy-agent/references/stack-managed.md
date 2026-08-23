<!-- Ported from #r-managed of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook F — Managed hyperscaler container stack

Best for serious production: managed compute + managed DB + queue + object storage +
secrets + identity + monitoring. Run `common-first-steps.md` before this file.

### Step 1 — Create separate environments `[HUMAN]`
- **Minimum:** staging and production resource groups/projects.
- **Stronger:** separate accounts/projects/subscriptions.
> Create these in the cloud console. Tell me which level you want and confirm once
> created.

### Step 2 — Map architecture to managed services `[AUTO]`
You need equivalents for container runtime, Postgres, queue, object storage, secret
manager, identity and logs/metrics. AWS/GCP/Azure names differ; the architecture does
not.

### Step 3 — Decide console vs Infrastructure as Code `[AUTO]` propose a default, state it
- **Beginner:** build first environment in console and document every setting.
- **Repeatable:** Terraform/Pulumi/cloud-native IaC from the start.
Propose based on whether this profile needs repeatable multi-environment provisioning,
state the reasoning in one line, proceed unless the user objects.

### Step 4 — Make data services managed/private `[HUMAN]`
> Managed Postgres and object storage should normally not be publicly exposed. Set up
> private networking or controlled service access in the console. Confirm once done.

### Step 5 — Design async execution `[AUTO]`
API persists job → publishes queue message → worker consumes → updates status → UI
reads/streams status.
- **Queue choices:** cloud-native queue, Redis queue, or workflow service for more
  complex durable orchestration.

### Step 6 — Implement least-privilege IAM `[HUMAN]`
> Separate runtime identities and give each only the actions it needs — this is an IAM
> console/policy action. Confirm once the policies are in place.

### Step 7 — Implement private networking if required `[HUMAN]`
> Set up VPC/VNet, private endpoints/connectors and controlled egress for internal
> warehouses/APIs. Confirm once configured.

### Step 8 — Choose multi-tenant isolation model `[AUTO]` propose a default, state it
- **Shared DB + tenant_id/RLS:** simplest.
- **Schema per tenant:** stronger separation, more ops.
- **DB per tenant:** strongest logical isolation, highest cost/ops.
Apply the same tenant boundary to vector data, object paths, caches, traces and tool
credentials. Propose based on the profile's `multitenant`/`residency`/`sensitive` flags,
state the reasoning in one line, proceed unless the user objects.

### Step 9 — Create release pipeline `[AUTO]`
PR → tests/evals → immutable image → vulnerability scan → staging → integration test →
production → smoke test.

### Step 10 — Define rollback and disaster recovery `[AUTO]` propose a default, state it / `[HUMAN]` confirms RPO/RTO
Know how to roll back code and how to restore DB/files. Define acceptable RPO/RTO when
the business requires it — that number is a business decision, so confirm it with the
user rather than assuming one.
