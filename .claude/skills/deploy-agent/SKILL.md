---
name: deploy-agent
description: Analyzes an agent project's capabilities, recommends a production deployment stack, and then guides the user step by step through actually deploying it — pausing for human action wherever a console click, external credential, or judgment call is needed. Use when the user wants to take an agent to production, asks "how do I deploy this", or invokes /deploy-agent.
disable-model-invocation: true
argument-hint: [path-to-agent-repo]
---

# Deploy Agent — capability profile → stack recommendation → guided go-live

`disable-model-invocation: true` is deliberate: this skill has real side effects — it
creates real GitHub repos, writes files into the target project, and its `[HUMAN]` steps
walk the user through provisioning real cloud resources and spending real money. It must
never auto-fire on casual phrasing like "how do I deploy this" — only on an explicit
`/deploy-agent` invocation.

This skill is the single command that ties together everything else in this bundle:
`repo-capability-scanner` (subagent) → `scripts/score_stack.py` (deterministic ranking) →
one of the `references/stack-*.md` runbooks (guided execution).

The canonical source of truth for *why* each capability matters and *why* each stack wins
or loses on it is `docs/deployment-decision-guide.html` in this repo (or wherever the user
has placed it) — the capability keys, scoring weights, and runbook steps below are ported
directly from it. If anything here ever looks inconsistent with that file, the HTML is
correct and this skill's content is stale; say so rather than guessing.

## Step 0 — Resolve the target

`$ARGUMENTS` is the path to the agent's repo/folder — call this `target_path` for the rest
of this skill. If empty, use the current working directory and confirm that's intended
before proceeding. In a monorepo with several agent projects, `target_path` is the specific
project subfolder (e.g. `agents/incident-agent`), not the monorepo root — everything this
skill writes (Step 5) is scoped under `target_path`, so running it against different
projects never collides.

## Step 1 — Detect capabilities (delegate, don't do it yourself)

Delegate to the `repo-capability-scanner` subagent with the target path. It returns a YAML
block: detected values for `uiType`, `duration`, `modelMode`, `authMode`, the boolean `caps`
map, an `evidence` map, and an `uncertain` list.

Do not re-derive capabilities yourself by reading the whole repo in the main context —
that's what the subagent is for. If the scanner reports the path isn't a recognizable
project, stop and tell the user, don't guess.

## Step 2 — Confirm the detected items

Show the user a compact table: capability → detected value → evidence. Ask them to confirm
or correct it in one pass — don't turn this into twenty separate questions. Something like:

> Based on the code, here's what I found. Reply with any corrections, or "looks right" to continue.
> | Capability | Detected | Evidence |
> |---|---|---|
> | Interface | Streamlit | `app.py` runs `streamlit run` |
> | Local SQLite state | Yes | `sqlite:///./data/app.db` in `db.py:12` |
> | Background workers | No | — |
> | ... | | |

## Step 3 — Ask only about what code can't tell you

For every key the scanner marked `"uncertain"`, ask a **targeted, closed-ended** question —
never a generic "tell me about your requirements." These are always business/judgment calls,
not code facts, so batch them into one short round:

- **duration** (if uncertain): "What's the longest a single run typically takes — under 30s,
  30s–15min, 15min+, or hours/resumable?"
- **users**: "Roughly how many people will use this at the same time, at peak — 1–5, 5–50,
  50–500, or 500+?"
- **multitenant**: "Will this serve multiple separate companies/customers whose data must
  stay isolated from each other, or just one team/org?"
- **sensitive**: "Does it handle PII, regulated, or confidential customer/company data?"
- **private**: "Does it need to reach anything only available on a private network/VPN
  (internal APIs, a warehouse, an on-prem system)?"
- **residency**: "Any formal requirement for data to stay in a specific region, or a
  compliance framework (SOC 2, HIPAA, etc.) that applies?"
- **commercial**: "Is this for external/paying customers, or internal use?"
- **tier**: "What's the budget posture — free/$0-first, paid-hobby/small-team, or
  full-scale production?" *(This one is never inferable and always required.)*
- **alwayson / ha / bursty**: only ask if not already implied by `tier=prod` or the
  `users` answer.

If the person doesn't know the answer to a judgment question (common for `residency` or
`sensitive`), default it to `false`/`"none"` and say so explicitly rather than blocking.

## Step 4 — Score and recommend

Write the confirmed profile to a temp JSON and run:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/score_stack.py /tmp/deploy-profile.json
```

This is a deterministic port of the HTML tool's own scoring algorithm — use it, don't
estimate the ranking yourself. Present the top result as **Recommended**, anything within
5 points as **Viable alternative**, everything else as **Poor fit** — matching the three
tiers the script already outputs.

For the recommended stack (and any viable alternative the user asks about), pull the
pros/cons from this table (identical to §03 of the HTML guide) so the user sees the
trade-off, not just a name:

| id | Best when | Pro | Con | Complexity |
|---|---|---|---|---|
| stream | Demo/learning/tiny internal tool | Fastest, easiest | Weakest control over auth/networking/workers | Very low |
| paas | Small-team production, ordinary web app | Very little ops, Git-based deploy | Platform limits; advanced workers/networking add cost | Low |
| cloudrun | Containerized API/UI, bursty traffic | Autoscaling + revisions, low server ops | State must be external; long jobs need separate design | Low–medium |
| vercel | Polished frontend + separate agent API | Excellent frontend workflow | Two deployments; auth/CORS/streaming wiring | Medium |
| vm | Local disk, browser/code execution, persistent workers | Maximum flexibility, simple mental model | You operate the server; single failure domain | Medium |
| managed | Commercial production, private networking, SSO | Managed IAM/networking/DB/queue/observability | More cloud concepts and cost | Medium–high |
| k8s | Many services, platform team, large scale | Maximum control and flexibility | Highest complexity, often unnecessary | High |

State the recommendation plainly, then **ask for explicit confirmation** before proceeding —
the user can accept the top pick or pick a different one from the list. Do not proceed to
Step 5 without this confirmation.

## Step 5 — Persist the decision

Write the confirmed profile + chosen stack to **`${target_path}/.claude-deploy/profile.md`**
— always inside the project you were pointed at (`$ARGUMENTS`), never relative to wherever
this skill happens to be installed. This matters if `deploy-agent` is installed once (e.g.
in `~/.claude/`) and reused across multiple agent projects in a monorepo — each project's
decision record has to live with that project, not in one shared file that the next
`/deploy-agent` call on a different project would silently overwrite.

Include: date, target path, chosen stack id, the full confirmed profile, and a one-line
rationale (top score vs. runner-up and why).

## Step 6 — Load the matching runbook and execute it, guided

Read `references/stack-<id>.md` for the chosen stack. It's a numbered list of steps, each
tagged `[AUTO]` or `[HUMAN]`:

- **`[AUTO]` steps**: you have the tools to do these yourself (write files, run local
  commands, `git` operations, local Docker builds). Do them, show the result concisely,
  and move to the next step without waiting — unless the step itself says otherwise.
  Before generating any `Dockerfile`, `docker-compose.yml`, or `Makefile`, check that the
  relevant tool is actually installed (`docker --version`, `docker compose version`,
  `make --version`) — if something's missing, tell the user exactly what to install and
  wait for their confirmation before generating files that assume it exists.
- **`[HUMAN]` steps**: these require a console click, creating or configuring an external
  account/resource, pasting a secret, spending real money, or any action with an external
  or hard-to-reverse effect — **even if a CLI command could technically perform it.**
  Creating a real GitHub repo or provisioning a real cloud VM is `[HUMAN]` even though `gh`
  or `gcloud` could run in your Bash tool, because it has consequences outside this session.
  For these:
  1. State plainly and specifically what the human needs to do (exact menu path, exact
     value to enter, exact place to paste something) — not "set up your cloud account,"
     but "go to console.cloud.google.com → IAM & Admin → ... → click X."
  2. Stop and wait. Do not proceed, do not assume it's done.
  3. If the human asks a clarifying question, answer it, then re-ask for confirmation.
     Keep answering follow-ups until they explicitly confirm the step is complete
     ("done", "yes", or equivalent) — then move to the next step.
  4. Never mark a `[HUMAN]` step complete on their behalf.

Follow the runbook's own internal checks (`Check:` callouts) — if a check fails, stop and
troubleshoot with the user rather than continuing past a broken state.

If the chosen stack's reference file doesn't exist yet in this bundle, say so and point at
`references/README-remaining-stacks.md` rather than improvising a runbook from memory.

## Step 7 — Close out

At the end of the runbook, summarize: what's deployed, the live URL, where secrets live,
how to roll back, and what — if anything — is still manual (e.g. "you'll need to renew
the TLS cert manually" or "no CI/CD wired yet, deploys are still git pull + restart").
Update `${target_path}/.claude-deploy/profile.md` with the final state and the date it
went live.

## Non-negotiables across every step

- Never invent a capability answer the scanner marked uncertain — always ask.
- Never silently skip a `[HUMAN]` step because "it's probably fine."
- Never fabricate a provider price, free-tier limit, or API detail — if the runbook
  doesn't specify one and it matters, say you're not certain and suggest the user verify
  on the provider's current pricing page rather than stating a number with confidence.
- Never proceed past Step 4 without explicit stack confirmation, and never proceed past
  any `[HUMAN]` step without explicit completion confirmation.
