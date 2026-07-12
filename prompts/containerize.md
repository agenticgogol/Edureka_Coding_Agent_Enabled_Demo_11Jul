---
description: Generate a Dockerfile, docker-compose.yml, and/or Makefile for an already-built project/concept/teaching demo. Checks Docker/Compose/Make prerequisites first and stops if any are missing.
argument-hint: <projects|concepts|teaching> <slug> [dockerfile|compose|makefile ...]
---

Parse `$ARGUMENTS` as `<kind> <slug> [targets...]` (kind is `projects`,
`concepts`, or `teaching`; targets are optional — one or more of
`dockerfile`, `compose`, `makefile`; if omitted, ask the user which they
want rather than generating all three by default).

## Preconditions

- `$1/$2/` must exist and have a working local run path — for
  `projects`/`concepts` that means `run-and-verify` has passed at least
  once (check the README's run/testing section); for `teaching`, that
  `teaching-verify` has passed at least once. If there's no evidence it
  runs locally yet, tell the user and stop — containerize what already
  works, don't use this to paper over a build that doesn't run.

## Stages

1. Invoke `containerize-project` against `$1/$2/`, scoped to whichever
   target(s) were requested (or clarified in step 0 if none were passed).
2. It will: study the folder to detect the actual stack and run
   command(s), check that Docker/Compose/Make are actually installed and
   the Docker daemon is running, **stop and tell the user exactly what to
   install/start if anything is missing**, then generate only the
   requested files, verify with a real `docker build`, and report the
   exact commands to build and run.

This command is independent of `/run-pipeline` and `/run-teaching-pipeline`
— call it any time after the project already works locally, as many times
as needed (e.g. once for a Dockerfile, later again if you also want a
Makefile).
