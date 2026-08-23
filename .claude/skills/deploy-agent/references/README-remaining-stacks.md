# Authoring the remaining stack runbooks

`stack-vm.md` is the fully worked template — same shape, same tagging convention
(`[AUTO]` / `[HUMAN]`), same "propose a default, state it, confirm" pattern for judgment
steps. Use it as the pattern. The other six pull from these exact sections of
`agent_production_deployment_decision_guide_v3.1.html` (repo root) — don't re-derive the
steps from general knowledge, port them:

| File to create | HTML section id | HTML heading |
|---|---|---|
| `stack-streamlit.md` | `#r-streamlit` | Runbook A — Streamlit / Gradio managed hosting |
| `stack-paas.md` | `#r-paas` | Runbook B — Managed PaaS |
| `stack-cloudrun.md` | `#r-cloudrun` | Runbook C — Cloud Run + managed state |
| `stack-vercel.md` | `#r-vercel` | Runbook D — Vercel frontend + separate agent API |
| `stack-managed.md` | `#r-managed` | Runbook F — Managed hyperscaler container stack |
| `stack-k8s.md` | `#r-k8s` | Runbook G — Kubernetes |

Also pull the provider-by-budget specifics for each from `#providers` (§03b) where
relevant — e.g. `stack-paas.md` should fold in the Render free vs. Render Starter vs.
Railway Hobby comparison the same way `stack-vm.md` folds in the Oracle/GCP/AWS comparison.

## Tagging rule (apply while porting)

Anything that is: a console click, creating/configuring an external account or resource,
pasting a secret, spending money, or SSHing into/configuring a remote machine → `[HUMAN]`,
with the exact thing to say to the user and an explicit wait for confirmation.

Anything Claude can do itself with local tool access (writing files, local `git`/`docker
build`, editing code) → `[AUTO]`, executed without waiting unless the step says otherwise.

Decision/judgment steps that aren't pure execution (e.g. "one-process vs web+worker
architecture" in the PaaS runbook) → `[AUTO]`, but written as "propose the default given
the profile, state the reasoning in one line, proceed unless the user objects" — the same
pattern as Step 2 in `stack-vm.md`.

Only these two tags exist — `[AUTO]` and `[HUMAN]`. There is no `[DELEGATE]` tag: this
skill is the only deployment skill in the repo, so nothing gets handed off to a lighter
tool elsewhere.

Before any `[AUTO]` step generates a `Dockerfile`, `docker-compose.yml`, or `Makefile`,
check that the relevant tool is actually installed (`docker --version`, `docker compose
version`, `make --version`) — if something's missing, tell the user exactly what to
install and wait for their confirmation before generating files that assume it exists.
Same habit as `stack-vm.md` Step 3 — apply it wherever a runbook generates these files.

`stack-vercel.md` and `stack-paas.md` will each need their own `[AUTO]` step that writes
platform config directly (`vercel.json` / a `render.yaml` or equivalent) rather than only
describing a console click — there's no separate config-generation skill to lean on
anymore, so the runbook itself has to produce the file.

## Also port

- `capability-glossary.md` — a condensed version of Appendix A (`#know` and `#why`,
  HTML lines ~134–320): the "what is this / how do I know / why it matters" content,
  for the *user's* clarifying questions in SKILL.md Step 3 — when a question needs more
  than one sentence of context, this is what to draw from instead of improvising.
- `provider-picks.md` — a direct port of §03b (`#providers`): the 🟢/🟡/💲/🏭 certified
  provider tables. Every stack runbook's provider-choice step should cite this file rather
  than inventing prices or free-tier limits — and it should carry the same "verify before
  you build, these move fast" caveat the HTML has in its Volatility Watch callout.

If asked to generate these, do it by reading the actual HTML file at
`agent_production_deployment_decision_guide_v3.1.html` (repo root) — don't reconstruct
the content from memory of what a typical deployment guide contains. The value of this
whole kit is that it says exactly what that document says, not an approximation of it.
Note: `deployment_manifest.html` also at repo root is an earlier stale draft — ignore it.
