# Stage 4: Tools & Authorization Boundary

All tools in this system are **custom, local, in-house logic** — none call a third-party API or SaaS. Per the brief's non-goals (no real Jira/GitHub/PagerDuty integration), there is nothing to source externally, so `agent-decision-external-tool-sourcing` is not invoked for any tool in this inventory.

## Tool inventory

| Tool | Sourcing | Read/Write | Reversible? | Auth tier | Idempotent? | Audited? |
|---|---|---|---|---|---|---|
| `search_similar_incidents` (embedding/keyword similarity lookup over the past-incidents audit store) | Custom | Read | n/a | No gate | Yes (pure lookup) | Yes — which precedent (if any) was matched and used is part of the incident record |
| `list_repos` | Custom | Read | n/a | No gate | Yes (pure lookup) | No |
| `search_code` (grep/glob across the 3 synthetic repos) | Custom | Read | n/a | No gate | Yes (pure lookup) | No |
| `read_file` (read one file's contents) | Custom | Read | n/a | No gate | Yes (pure lookup) | No |
| `run_tests` (execute a repo's synthetic test file(s)) | Custom | Read + local execution, no persistent mutation | n/a (no state change) | No gate | Yes (deterministic given same code state) | Yes — result feeds ticket-closure decision |
| `draft_patch` (LLM-authored diff, held in memory/checkpoint, not yet written to disk) | Custom | Read (produces a proposal, doesn't touch the filesystem) | n/a | No gate | Yes | Yes — proposal is part of the incident record |
| `create_jira_ticket` (mocked — append to local JSON ticket store) | Custom | Write | Reversible (it's a local JSON record; can be corrected/reopened) | Service-scoped, no human approval | Yes (ticket-per-incident key prevents duplicate creation on retry) | Yes |
| `apply_patch` (write the approved diff to the real synthetic repo file(s) on disk) | Custom | Write | **Irreversible without an explicit undo step** (overwrites source file content; nothing auto-backs it up) | **Human approval required** | Yes (re-applying the same approved patch to already-patched code is a no-op / detected and skipped) | Yes — mandatory, this is the system's one consequential action |
| `close_jira_ticket` (mocked — update local JSON ticket store) | Custom | Write | Reversible (local JSON, can be reopened) | Service-scoped, no human approval — but only reachable after `run_tests` reports pass post-patch | Yes (closing an already-closed ticket is a no-op) | Yes |

## External tool sourcing decisions

Not applicable — every tool is custom/local. No third-party service is called anywhere in this system.

## Per-tool rationale

- `search_similar_incidents` — added after stage 5 review surfaced a new requirement: before doing full repo/file search, check the past-incidents store for a similar prior incident (by text similarity) and, if found, reuse its identified repo/root-cause-location as a shortcut — the agent still independently re-derives the code fix itself (it does not reuse a past patch verbatim), only the "which repo / which file" search cost is skipped. This is read-only against the audit history store, so no gate; it's audited so the incident record shows whether a precedent was used, which matters for explaining a fast-path answer.
- `list_repos`, `search_code`, `read_file` — pure read-only lookups over local synthetic files; no side effects, so no gate and no audit requirement beyond normal application logging.
- `run_tests` — executes code but doesn't persist any mutation (test runs don't alter repo state); still worth auditing because its pass/fail result is the deciding factor for ticket closure, and that decision should be traceable in the incident record.
- `draft_patch` — produces a proposal only; nothing is written to disk at this point, so it's classified as read-equivalent (side-effect-free) even though its *output* is a diff — the diff only becomes consequential once `apply_patch` runs.
- `create_jira_ticket` — mutates the mocked ticket store, but this is a low-stakes, easily-corrected local record (not a real external system with side effects on other teams), so it's service-scoped without requiring a human-approval pause; this matches the usecase's intent of "auto-generates a Jira ticket" as an automatic step, not one that needs sign-off itself.
- `apply_patch` — the one genuinely irreversible action in the system: it overwrites real file content in the synthetic repo with no automatic backup/rollback. This is exactly the tool stage 1's high-impact flag was tracking, and it's routed to **human approval required**, consistent with the brief's explicit HITL requirement ("proposed patch pauses for human-in-the-loop approval before being applied").
- `close_jira_ticket` — mutates the mocked ticket store, but its trigger condition (only reachable after tests pass post-patch, which itself only happens after human-approved `apply_patch`) means the human-approval gate on `apply_patch` already governs the path that leads here; a second approval gate on close would be redundant given the underlying action (the code fix) was already approved.

## Mismatches surfaced

None. Stage 1 flagged exactly one high-impact/irreversible action (patch application), and this stage confirms `apply_patch` is the only tool that meets that bar — every other tool is either read-only or a reversible local record mutation. No revisit of stage 1 is needed.

**Revision note (post stage-5 review):** the user asked for a precedent-cache capability — checking whether a similar past incident exists before doing full repo/file search, to skip that cost. This adds `search_similar_incidents` to the inventory above. It does not change stage 1-3's decisions (still single-agent, bounded ReAct, durable checkpointed runtime) — it's an additional read-only tool slotted into the existing loop as the agent's first search step. It does, however, mean stage 5's "long-term knowledge: not needed" call must be revisited, since a similarity-searchable store of past incidents is exactly a long-term-knowledge category — stage 5 is being re-run to reflect this.

## Carried-forward signals for later stages

- Tools requiring an audit trail: `search_similar_incidents`, `run_tests`, `draft_patch`, `create_jira_ticket`, `apply_patch`, `close_jira_ticket` (feeds stage 5's memory design — the incident history record needs a field for each of these events).
- Tools requiring human-approval state (pending/approved/rejected) to be tracked: `apply_patch` (feeds stage 5's task-state category and stage 7's loop interrupt point — this is the one and only interrupt in the graph).
- Capabilities declined or degraded due to external tool cost: none — nothing was sourced externally, so nothing was declined or degraded.
- New: `search_similar_incidents` requires the past-incidents store (stage 5) to be searchable by similarity, not just append-only-log-readable — feeds stage 5's storage-type decision directly.

## Status: APPROVED
