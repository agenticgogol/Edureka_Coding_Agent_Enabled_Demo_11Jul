<!-- Ported verbatim from #providers (§03b) of agent_production_deployment_decision_guide_v3.1.html -->

# 03b · Certified providers by budget tier

The stack archetypes are architecture-level. This is the vendor level: actual named
services for whichever tier you selected (`H. Deployment posture`), with the pros/cons
and known caveats verified as of August 2026.

**Tier legend**
- 🟢 Free — durable, no card, indefinite
- 🟡 Free* — free but capped, sleeps, or needs a card
- 💲 Hobby-paid — roughly $5–30/month
- 🏭 Production — managed, $100+/month, usually per-usage

> **Volatility watch — verify before you commit:** free tiers move fast. **AWS EC2's 750
> free hours/month no longer exist for accounts created after 15 Jul 2025** — new
> accounts get a $200 credit that expires in 6 months instead. **Oracle halved its
> Always Free Arm VM** (4 OCPU/24GB → 2 OCPU/12GB) in June 2026 with no announcement.
> **Fly.io, Railway and Koyeb no longer have permanent free tiers** (trial credit or
> ~$5/month minimum only) — do not plan around them as $0 options. Re-check the
> provider's own pricing page before you build.

## Compute — app hosting
- 🟢 **Render free web service** — Docker or native Python, managed Postgres available.
  *Con: sleeps after 15 min idle, 30–50s cold wake.*
- 🟢 **Streamlit Community Cloud / HF Spaces (CPU basic)** — no Dockerfile needed. *Con:
  HF Spaces sleeps after 48h idle; neither gives real auth or a custom domain easily.*
- 🟡 **Oracle Cloud Always Free VM (Arm)** — 2 OCPU/12GB, genuinely persistent, no sleep.
  *Con: card required for verification only; region is fixed at signup; allowance was
  just cut once.*
- 🟡 **Google Cloud Run** — scale-to-zero container, 2M requests/month free. *Con: card
  required; 60-min timeout; cold starts unless you pay for min-instances.*
- 💲 **Render Starter ($7/mo) / Railway Hobby ($5/mo) / Fly.io (~$8–25/mo)** — no sleep,
  easy Git deploy. *No major con at this budget — the easiest paid step up.*
- 🏭 **Cloud Run / ECS Fargate / Azure Container Apps** with autoscaling, VPC, IAM. *Con:
  real cloud-engineering surface area — budget for it, not a weekend project.*

## Relational state (replacing local SQLite)
- 🟢 **Turso (libSQL)** — SQLite-compatible, so existing queries mostly work unchanged;
  500M reads + 10M writes/month free. *No major con for most agents — this is usually
  the easiest migration path, not a rewrite.*
- 🟢 **Neon Postgres** — true scale-to-zero, unlimited branches, never expires. *Con:
  requires rewriting SQLite-specific SQL to Postgres dialect.*
- 🟡 **Supabase Postgres** — bundles auth for free too. *Con: pauses the free project
  after 7 days with no traffic.*
- 💲 **Any provider's paid Postgres add-on ($7–15/mo)**. *No major con — removes the
  pause/sleep behavior of the free tier.*
- 🏭 **Cloud SQL / RDS / Azure Database for PostgreSQL**, Multi-AZ, PITR backups. *Con:
  billed hourly regardless of traffic, roughly $100–250/month for an HA instance.*

## Vector / RAG storage
- 🟢 **pgvector on Neon/Supabase** — no extra vendor, transactional with your other
  data. *No major con — the default choice unless you outgrow it.*
- 🟢 **Qdrant Cloud free cluster (1GB)** — dedicated vector features (hybrid search,
  filtering). *Con: one more service to operate and secure.*
- 🏭 **Managed Pinecone / Qdrant / Weaviate Cloud** — scale, SLAs, enterprise features.
  *Con: another line item and another vendor relationship.*

## Files / blob storage
- 🟢 **Cloudflare R2** — 10GB free, zero egress fees. *No major con — this is why it's
  the default recommendation even outside Cloudflare's own compute.*
- 🟡 **S3 / GCS free tier** — 5GB free. *Con: egress is billed on both, unlike R2.*
- 🏭 **S3/GCS/Azure Blob at scale** with lifecycle policies and CDN. *No major con at
  production scale — this is the mature default.*

## Model inference — usually the largest bill, not hosting
Free inference is rate-limited, not unlimited, and every provider's free numbers are
moving targets:

| Tier | Options | Pro / con |
|---|---|---|
| 🟢 | **Google AI Studio (Gemini), Groq, Cerebras** — no card | Con: rate limits are tight (Groq ~30 RPM/1,000 RPD on Llama 70B) and providers have quietly cut free limits before (Gemini cut 50–80% in late 2025). **Never hardcode a model name** — providers also delete models from free catalogs without notice; resolve model IDs from config and pool 2+ providers with failover. |
| 💲 | **Pay-as-you-go API** (same providers, metered) | Con: no cap by default — set a spend limit/budget alert on day one. |
| 🏭 | **Enterprise agreement / Bedrock / Vertex private endpoint / provisioned throughput** | Con: minimum commitments — buys an SLA, a contractual no-training clause, and predictable latency under load. |

**Cost lever available at every tier:** route cheap/fast calls (classification,
extraction, routing) to a small model and reserve the expensive model for the actual
reasoning step — most agents can move 80–90% of calls down a tier with no quality loss.

## Observability — the free tier that's easiest to blow through by accident
🟢 **Langfuse Cloud Hobby** gives 50,000 units/month free — but a *unit* is every trace,
observation *and* score, not every request. A simple one-call agent is ~2 units per run;
a 15-step agent with evaluators is comfortably 20+ units per run. That's roughly 2,500
agent runs/month on the free tier, not 50,000. **Sample** — trace 100% of failures and
5–10% of successes — rather than logging every step of every run. 🟢 Grafana Cloud Free
and Sentry (5k errors/month) are genuinely free with no such trap.
