<!-- Ported from #r-k8s of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook G — Kubernetes

Do not choose Kubernetes because it sounds production. Choose it because workload/scale/
platform needs justify it. Run `common-first-steps.md` before this file.

### Step 1 — Prove all components with Docker first `[AUTO]`
If Compose is unreliable locally, Kubernetes will make diagnosis harder.

### Step 2 — Use managed Kubernetes `[HUMAN]`
> Prefer EKS/GKE/AKS or equivalent rather than self-building the control plane. Create
> the cluster in the cloud console and confirm once it's up.

### Step 3 — Keep critical state outside the cluster initially `[AUTO]`
Use managed Postgres/object/vector services unless your team already operates stateful
Kubernetes well.

### Step 4 — Create Deployment, Service and Ingress `[AUTO]`
Add resource requests/limits. Use Helm/Kustomize when environments multiply.

### Step 5 — Separate web pods and worker pods `[AUTO]`
Scale API by traffic and workers by queue depth. Persist run state externally.

### Step 6 — Use workload identity and external secrets `[HUMAN]`
> Avoid long-lived cloud credentials in ordinary Kubernetes Secrets when workload
> identity is available — set that up in the cloud console/IAM. Confirm once done.

### Step 7 — Add TLS, network policy and controlled ingress `[AUTO]`
Expose only required services and restrict pod-to-pod/egress paths for sensitive
workloads.

### Step 8 — Add autoscaling with limits `[AUTO]`
HPA/event-driven scaling plus max replicas/cost controls.

### Step 9 — Use controlled CI/CD or GitOps `[AUTO]` propose a default, state it
Argo CD/Flux if the team already uses GitOps; otherwise a simpler CI deploy is
acceptable. Propose based on whether the profile implies an existing platform team,
state the reasoning in one line, proceed unless the user objects.

### Step 10 — Test pod/node failure `[HUMAN]`
> Delete a worker pod during a run, with me watching the outcome together. The job should
> recover safely from durable state. Tell me what you observe.
