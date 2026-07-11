---
name: agent-crewai
description: Use when design.md/project_brief.md explicitly names CrewAI for multi-agent orchestration. Do not substitute LangGraph — CrewAI is named because the syllabus/brief requires hands-on CrewAI, not "a multi-agent pattern."
---

# Agent (CrewAI)

CrewAI's API and idioms differ meaningfully from LangGraph (agents/tasks/
crew objects vs. explicit state graphs). This is exactly the kind of
narrower, faster-moving framework where the model's baseline knowledge is
thinner — start from the bundled reference and research-first before
writing code.

## When to use

- Brief/design names CrewAI explicitly.

## Procedure

1. **Research-first** (see `research-first` skill): fetch CrewAI's current
   official quickstart docs and diff against
   `references/basic_crew.py` in this folder — CrewAI's API has changed
   across versions (e.g. `Crew`/`Agent`/`Task` constructor args, process
   types). If they've diverged, update your understanding from the fetched
   docs, not just the bundled file.
2. Read and adapt `references/basic_crew.py` — a minimal known-working
   crew (2 agents, sequential process, one task each).
3. Scaffold under `projects/<slug>/backend/agent/` (or
   `concepts/<slug>/agent/`). Route all LLM calls through the copied
   `llm_client.py` (via `helper-utils`) — CrewAI supports custom LLM
   configs; wire in whichever real provider `require-api-key` verified
   rather than hardcoding one. No mock mode.
4. Expose one clean entrypoint (`run_crew(input) -> output`).
5. **Spike-first** (see `agent-builder` subagent): before wiring into the
   full project, run the adapted reference standalone and confirm it
   actually executes with the installed CrewAI version before building the
   rest of the integration around it.
