<!-- Condensed from #know and #why of agent_production_deployment_decision_guide_v3.1.html -->

# Capability glossary — for clarifying questions

One-line "what is this / how do I know / why it matters" per capability-profile item.
Draw from this when a clarifying question needs more than a bare label — don't
improvise the explanation.

**Primary interface (API only / Streamlit / Gradio / Next.js / existing app)**
What: how a person or system interacts with the agent. How do I know: "When I start the
agent locally, what do I open?" — a webpage built by Streamlit/Gradio/React means that
UI; an HTTP endpoint called by another app/Postman means API-only. Why it matters:
API-only fits managed API/container runtimes; Streamlit/Gradio can often be one Python
service; Next.js/React often benefits from a separate frontend + agent API; an existing
enterprise UI means focus on the authenticated API, not UI hosting.

**Token/event streaming to the UI**
What: the user sees the answer appear gradually instead of waiting for the complete
response. How do I know: ask a long question locally — words/status appearing
incrementally means streaming. Why it matters: requires a proxy/runtime that supports
long-lived SSE/WebSocket connections without buffering, which can rule out or complicate
some edge/serverless paths.

**Reusable API for other systems/clients**
What: a machine-to-machine entry point another website, app, bot or service can call.
How do I know: "Can something other than my current UI call the agent over HTTP?" Why it
matters: other clients need a stable backend contract, auth, versioning and rate
limiting — a UI-only host becomes less attractive.

**Run duration**
What: wall-clock time from request to finished run, measured on realistic (not fastest)
cases. Why it matters: <30s runs almost anywhere; 30s–15m needs attention to request
timeouts; >15m usually needs a worker/job; hours/resumable needs durable workflow state
plus event-driven resume.

**Human-in-the-loop approval / pause and resume**
What: the agent stops and waits for a person to approve/reject/modify before continuing,
potentially for minutes or hours. How do I know: can the workflow stop, wait, and later
resume from that same point? A confirmation popup that continues in the same request
doesn't count. Why it matters: don't keep a server process waiting for hours — save a
checkpoint, stop compute, resume later; needs durable state and often async execution.

**Background workers / queue**
What: a separate process performs work after the web request returns; a queue holds jobs
waiting for it. How do I know: "If the user closes the browser after submitting a task,
should the task continue?" Why it matters: requires a platform supporting another
process or a managed worker/job service — simple single-process hosts may not fit.

**Scheduled or event/webhook execution**
What: the agent starts automatically (time-based, or on an external event/webhook), not
by a user pressing a button. Why it matters: can favor serverless/jobs since compute only
runs when triggered — an always-on web server may be unnecessary.

**Local SQLite / local persistent files**
What: important data written to files on disk that must still exist later. How do I
know: copy only the source code to a fresh folder/machine — if the agent loses memory or
fails without the local DB/data files, this applies. Why it matters: ephemeral hosts can
erase local files; either migrate state to managed DB/object storage or choose a
persistent VM/volume.

**Conversation history / long-term memory / checkpoints**
What: the system remembers something after one interaction finishes. How do I know:
stop the app completely, restart, reopen an old conversation/run — if old state should
still be there, you need durable memory/checkpoint storage. Why it matters: these need
durable storage but not necessarily a durable server — externalize them and stateless
compute stays viable.

**RAG / vector search**
What: the agent searches your own documents/data for relevant chunks (often via
embeddings) before answering. How do I know: does it index documents and later retrieve
semantically similar passages? Sending a whole PDF directly to an LLM doesn't count. Why
it matters: adds a durable index and ingestion pipeline — pgvector minimizes service
count, a dedicated vector DB adds another managed component.

**Uploads or generated file artifacts**
What: the system accepts or creates files (uploads, generated reports/exports) that must
be available later. How do I know: does the app write these to a local folder and expect
them in a later request/session? Why it matters: temporary local files are unsafe on
many PaaS/serverless products — usually move them to object storage.

**Headless browser / Playwright / scraping**
What: the agent launches a real browser engine programmatically (opens pages, clicks,
renders JS, scrapes). How do I know: calling HTTP APIs or downloading pages with
`requests` is *not* this; launching Chrome/Chromium or automating clicks is. Why it
matters: needs native binaries, RAM and subprocess support — containers/VMs are safer
than tiny edge runtimes.

**Executes arbitrary/generated code or shell commands**
What: the agent runs code or terminal commands created dynamically at runtime. How do I
know: look for `subprocess`, `os.system`, shell execution, notebook kernels,
sandbox/container execution, or dynamic `exec`/`eval`. Why it matters: requires a sandbox
boundary and resource/network limits — a strong reason for dedicated container/VM
execution rather than the main web process.

**Self-hosted/local MCP servers**
What: MCP servers exposing tools/resources that your own deployment must also run,
rather than calling someone else's remote MCP endpoint. How do I know: do you start
another MCP process/server yourself, or invoke one from your own repo? Why it matters:
remote MCP is just a network call; local MCP creates extra processes/services, favoring
multi-service PaaS, VM or Kubernetes.

**Heavy document/OCR/media processing**
What: work using significant CPU/RAM or native programs outside ordinary Python request
processing (OCR, PDF/image conversion, ffmpeg, large embedding batches). How do I know:
does your laptop's CPU/RAM jump noticeably, do tasks take minutes, did you install
Tesseract/Poppler/ffmpeg? Why it matters: needs more memory/CPU and native packages,
which can rule out small free hosts and edge functions.

**Hosted LLM API vs self-hosted CPU/GPU model**
What: where the model actually runs — hosted API (OpenAI/Anthropic/Gemini/Groq, HTTPS
requests), self-hosted CPU (Ollama/vLLM/Transformers, no GPU), or self-hosted GPU
(CUDA/GPU hardware). How do I know: need an API key with no local weights → hosted; you
download weights and serve inference locally → self-hosted. Why it matters: hosted keeps
the app lightweight; self-hosted CPU needs a persistent high-RAM service; GPU needs
GPU-capable infra and usually a separate model-serving layer.

**No auth / normal login / enterprise SSO**
What: who's allowed in and how they prove identity — no auth (anyone with the URL),
normal login (email/password, Google/GitHub, magic link), enterprise SSO (corporate
Okta/Entra ID, SAML/OIDC). Why it matters: no-auth demos fit simple hosts; normal
OAuth/email works widely; enterprise SSO adds identity integration, custom domains and
sometimes private networking.

**Multiple tenants / organizations with strict isolation**
What: one deployment serves multiple companies/orgs, and Company A must never see
Company B's data. How do I know: only individual users inside one company/team → likely
not needed; selling the same SaaS agent to many companies with separated
data/accounts → needed. Why it matters: tenant isolation must cover DB rows, vector
data, files, caches, traces, quotas and tool credentials — raises the minimum
platform/security bar.

**PII / confidential / regulated / customer data**
What: data whose exposure would matter legally, contractually or reputationally
(customer names/emails, employee data, financial/medical records, internal docs,
credentials). How do I know: "Would my company/customer care if this prompt, file or
trace were exposed?" Why it matters: changes acceptable providers, contracts, logging,
model data handling, encryption and access controls — hobby/free tiers may be unsuitable
even if technically capable.

**Private network / VPC access**
What: some database/API is intentionally unreachable from the public internet, only from
a company/cloud private network. How do I know: does your local agent need VPN access to
reach a warehouse, internal API, private DB hostname or corporate system? Why it
matters: the runtime needs compatible VPC/VNet/private endpoint connectivity.

**Data residency / formal compliance**
What: rules requiring data to stay in certain countries/regions or systems to meet
standards/contracts. How do I know: has security/legal/compliance stated requirements
like "EU only," SOC 2, HIPAA, ISO controls, audit requirements? Why it matters: may
require specific regions, audit controls and approved enterprise services, narrowing
provider choices.

**Expected concurrent users**
What: people actively using the agent at roughly the same time, not total registered
users. How do I know: estimate a rough peak (e.g. for 100 employees, maybe 5–15
simultaneous) — choose the next larger band if unsure. Why it matters: 1–5 lives on one
small instance; 50–500 benefits from autoscaling/external state; 500+ needs load
testing, queue/DB pool planning and managed scale.

**Cold starts / sleeping are unacceptable**
What: cheap/serverless platforms stop idle services; the first request after idle can
take extra seconds. How do I know: "Would users complain if the first request after
inactivity sometimes takes 10–60 seconds longer?" Why it matters: sleeping/scale-to-zero
hosts become poor fits — use minimum replicas or an always-on VM/service and accept
baseline cost.

**High availability / uptime expectation**
What: the app should keep working even if one server/process fails. How do I know: is
downtime merely inconvenient for a small internal tool, or do customers/revenue/workflows
depend on it? Why it matters: a single VM/instance is a failure domain — HA needs
multiple stateless replicas plus redundant managed state.

**Bursty or unpredictable traffic**
What: usage can jump suddenly (e.g. 2 req/min most of the day, 100 at once after a
meeting/campaign). How do I know: steady/tiny usage → a fixed VM is fine; sudden crowds
or hard-to-predict volume → select this. Why it matters: autoscaling/serverless can be
efficient, but agents can create expensive spikes — cap maximum scaling and budgets.

**Commercial / external-customer use**
What: the system is part of a business product/service or exposed to customers, not only
a private learning demo. How do I know: do customers, clients, advertisers, merchants or
external orgs use it, or does your company rely on it operationally? Why it matters:
affects plan eligibility, SLA/support expectations, contracts, data terms and
operational rigor.

**Free / hobby-paid / full-scale production (deployment posture)**
What: not a technical feature — how much operational compromise you'll accept. Free:
learning/demo/personal, okay with sleep/quotas/manual work. Hobby-paid: small
internal/team app, willing to spend modestly for easier ops. Full-scale:
business-critical/customer-facing, reliability/security/support matter more than cost.
How do I know: would you be upset but not materially harmed by downtime (hobby may be
enough), or do customers/business processes depend on it (choose full-scale)? Why it
matters: free optimizes for $0 and accepts limits; hobby-paid buys simplicity; full
production prioritizes reliability/security/networking/support over minimizing spend.
