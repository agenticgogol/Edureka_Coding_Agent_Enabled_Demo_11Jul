---
description: Study an already-built project/concept/teaching demo and recommend how to deploy it — Vercel-only, Vercel + GitHub Actions, or Vercel + Render/Railway — with a step-by-step manual walkthrough. Advisory only, generates no files by default, takes no deployment action.
argument-hint: <projects|concepts|teaching> <slug>
---

Parse `$ARGUMENTS` as `<kind> <slug>` (kind is `projects`, `concepts`, or
`teaching`).

## Preconditions

- `$1/$2/` must exist and have a working local run path — check the
  README's run/testing section for evidence `run-and-verify` (or
  `teaching-verify`) has passed at least once. If not, tell the user and
  stop; a deployment plan for code that doesn't run locally yet is
  guesswork.

## Stages

1. Invoke `deployment-advisor` against `$1/$2/`. It studies the actual
   architecture (frontend framework, backend, statefulness, long-lived
   connections, background jobs, external managed dependencies, CI needs)
   and classifies it into one of three tiers, stating the specific factors
   that drove the call.
2. It presents the tier, what runs where, and a concrete step-by-step
   manual walkthrough to get it live on the recommended platform(s).
3. It generates no config files and deploys nothing. If the user wants to
   proceed, it names the next skill explicitly — `deploy-config` for
   `vercel.json`/`render.yaml`, or `containerize-project` if a
   Dockerfile/Compose/Makefile fits the chosen platform better.

This command is independent of `/run-pipeline` and `/run-teaching-pipeline`
— call it any time after the project already works locally.
