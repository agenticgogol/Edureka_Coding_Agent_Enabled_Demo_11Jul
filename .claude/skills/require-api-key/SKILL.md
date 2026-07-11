---
name: require-api-key
description: Use as the FIRST gate in every pipeline (projects, concepts, teaching) after the brief is confirmed, before any design or code is written. Confirms a real, working LLM API key is present — no mock mode exists in this repo; nothing builds without a verified key.
---

# Require API Key

This repo does not have a mock mode. Every project, concept, and teaching
demo calls a real model provider, so nothing gets built, run, or verified
without a working key. This skill is the hard stop that enforces that
before any other work starts.

## When to use

- Immediately after a brief (`project_brief.md` / `concept_brief.md` /
  `teaching_brief.md`) is confirmed, before `technical-design` /
  `teaching-build` / any code-writing skill runs.
- Re-run if a key ever stops working mid-session (expired, rate-limited,
  revoked) — treat that the same as "no key," stop and get a working one
  before continuing.

## Procedure

1. Check `.env` (project-level if it exists, else the repo-root
   `.env.example`'s copy) for at least one of: `ANTHROPIC_API_KEY`,
   `OPENAI_API_KEY`, `GROQ_API_KEY` (or whatever provider `design.md` /
   the brief specifies).
2. If none is set: **stop immediately.** Tell the user exactly which
   variable(s) to set in `.env` and where to get a key (provider's API key
   page). Do not draft `design.md`, do not write any code, do not create
   placeholder/stub implementations "for now." There is nothing to build
   until this is resolved.
3. If a key is present, **verify it actually works** — make one small,
   cheap real API call (e.g. a 1-token completion) using the exact client
   the project will use (`_shared/llm_client.py`'s provider path). Do not
   assume a present key is a valid key.
4. If the verification call fails (bad key, expired, insufficient quota,
   wrong permissions): report the exact error to the user and stop. Do not
   proceed, and do not silently fall back to anything — there is no
   fallback path in this repo.
5. Only once a real call has succeeded, proceed to the next pipeline
   stage. Record which provider/model was verified in the project's
   README so later steps (and the user) know what's actually being used.
