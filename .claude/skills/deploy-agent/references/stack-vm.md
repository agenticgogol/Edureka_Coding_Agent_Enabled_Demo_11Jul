<!-- Ported from #r-vm of agent_production_deployment_decision_guide_v3.1.html -->

# Runbook E — Single VM + Docker Compose + Caddy

Ported from §09 of the HTML guide, with the §03b provider picks folded into Step 1.
Good fit when: persistent local disk, headless browser, shell/code execution, self-hosted
MCP servers, or always-running background workers are needed. Run `common-first-steps.md`
before this file.

### Step 1 — Choose a VM provider for the confirmed budget tier `[HUMAN]`
Relay this to the user, don't pick for them:

> Based on your budget tier (**{tier}**), here are the options:
> - **Free** → Oracle Cloud Always Free (Arm, 2 OCPU/12GB) — the only genuinely permanent
>   free VM at this size. A card is required for identity verification only, not charged.
>   Region is fixed at signup and can't be changed later — pick one close to your users.
> - **Hobby-paid** → a $5–8/month VM (DigitalOcean, Hetzner, a small Lightsail/Compute
>   Engine instance) — simpler than Oracle's region/capacity quirks.
> - **Do not assume AWS EC2 is free** — the 750-hour/month tier only applies to accounts
>   created before 15 Jul 2025; newer accounts get a 6-month credit that then bills
>   normally.
>
> Which provider do you want to use, and do you already have an account?

Wait for their answer before continuing — the exact commands in later steps assume you
know which provider and whether SSH access is already set up.

### Step 2 — Decide the state strategy `[AUTO]`
Propose a default and state it, rather than asking another open question:
- If the profile shows `localstate: true` and no `ha`/`multitenant` requirement: recommend
  keeping SQLite/files on a persistent VM volume with off-machine backups (simplest).
- Otherwise: recommend managed Postgres/object storage so the VM itself stays replaceable.
For SQLite specifically, note that backups must use an SQLite-safe method (the `.backup`
command or Litestream), not a raw file copy while the process may be writing.

### Step 3 — Create Docker Compose locally `[AUTO]`
Before generating anything, check that Docker/Compose are actually installed
(`docker --version`, `docker compose version`) — if either is missing, tell the user
exactly what to install and wait for their confirmation before generating files that
assume it exists.
Write `docker-compose.yml` with the services the profile implies: `web` (always), `worker`
(if `background: true`), `postgres`/`redis` (if the state decision needs them), `caddy`
(always, for TLS termination in Step 8).
**Check:** `docker compose up` reproduces the whole app on your own machine before you
touch a remote server.

### Step 4 — Provision the Linux VM `[HUMAN]`
> On {provider}: create an SSH key pair if you don't have one, create the VM (ensure enough
> RAM for your workload), allow inbound 80/443, restrict SSH as tightly as your workflow
> allows, then SSH in once and run your distro's update command. Tell me the VM's public
> IP/hostname and confirm you can SSH in — I'll give you the exact commands to run once
> you're connected.

### Step 5 — Install Docker on the VM `[HUMAN]`
Give the user Docker's official install command for their distro to paste over their own
SSH session (you don't have direct network access to their new VM). Confirm Docker is
running and enabled at boot before moving on.

### Step 6 — Clone the repo onto the VM `[HUMAN]`
```bash
cd /opt
git clone <repo-url> agent-app
cd agent-app
```
Use an HTTPS deploy token or SSH deploy key — either is fine. Confirm the clone succeeded.

### Step 7 — Create production `.env` on the VM `[HUMAN]`
> Create `/opt/agent-app/.env` on the VM with production values (`chmod 600`), copying
> from your local `.env` but rotating anything that was ever committed to git history.
> Never paste secrets into this chat — just confirm when it's done.

### Step 8 — Start services `[HUMAN]`
```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=200
```
Confirm all services show healthy/running before continuing.

### Step 9 — Add the HTTPS reverse proxy `[HUMAN]`
Caddy is the simplest path (automatic TLS). This step also needs a DNS record pointed at
the VM's IP — that's a registrar/DNS console action, definitely `[HUMAN]`. Confirm the
domain resolves and serves valid HTTPS before moving on.

### Step 10 — Back up off the VM `[HUMAN]`
> Set up SQLite backup-command-or-Litestream (or scheduled `pg_dump` if you migrated to
> Postgres) writing to object storage off this VM. Then **restore once, on a throwaway
> path, to prove the backup is actually usable** — a backup that's never been restored is
> unverified. Confirm both the backup and the test restore succeeded.

### Step 11 — Automate deploys
`[AUTO]`: write a GitHub Actions workflow that SSHes in, does `git pull && docker compose
up -d --build`, and hits `/health` afterward.
`[HUMAN]`: add the SSH private key and host details as GitHub Actions repo secrets (a
console paste action) — confirm before the workflow is trusted to run.

### Step 12 — Monitor the host and agent `[AUTO]`
Since this typically runs on the user's own machine with normal network access, curl the
public health endpoint yourself and report the result. Note what's still manual (e.g. "no
alerting wired up yet — you'll need to check `docker compose ps` yourself until you add
one") rather than implying more automation exists than actually does.

---
**Go-live summary to give the user at the end:** live URL, where `.env`/secrets live,
how to redeploy (`git push` → Action, or manual `git pull && compose up -d --build`), how
to roll back (checkout previous commit, redeploy), and confirmation the backup was
restore-tested.
