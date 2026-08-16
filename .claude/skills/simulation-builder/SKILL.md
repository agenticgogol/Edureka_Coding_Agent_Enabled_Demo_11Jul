---
name: simulation-builder
description: MUST USE when eval/tasks.md contains multi-turn/stateful tasks and the user wants multi-turn testing — "simulate conversations", "persona testing", "multi-turn eval", "eval/simulation/". Only applies to multi-turn/stateful task shapes — skip entirely if none exist. Trigger eagerly on any mention of simulating users, conversation trajectories, or persona-based agent testing.
---

# Simulation Builder

Produces `eval/simulation/` for multi-turn/stateful tasks only. If `eval/tasks.md` has no multi-turn/stateful tasks, tell the user this skill doesn't apply and stop.

## Steps

1. **Read `eval/tasks.md`** and pull every task tagged multi-turn/stateful.

2. **For each such task, build 3-5 personas.** Each persona needs:
   - goal (what the simulated user is actually trying to accomplish)
   - starting knowledge (what they already know/don't know)
   - emotional state (calm, frustrated, urgent, confused, etc.)
   - communication style (terse, verbose, indirect, technical, non-native phrasing, etc.)
   - hidden constraints (things the persona won't volunteer unless asked — e.g. a budget cap, a prior failed attempt)
   - a machine-checkable success condition (something a script can verify from the transcript, not just "felt resolved")

3. **Present the persona set for editing before writing** — let the user adjust personas per task, since these are judgment calls about what's realistic for the domain.

4. **Define trajectory judge criteria** that grade the WHOLE transcript, not turn-by-turn: escalation recognition (did the agent hand off when it should have), no re-asking for information the user already gave, goal resolution (was the success condition actually met), no looping (doesn't repeat the same step/question).

5. **Write the simulation config** (`eval/simulation/config.yaml` or similar) with:
   - max 8-10 turns hard stop per conversation
   - 5-10 runs per persona (persona behavior varies run to run)
   - simulator model explicitly set to a **different model family** than both the system-under-test and the judge (avoids self-preference bias contaminating the simulation)
   - non-zero temperature for the simulator (deterministic personas defeat the point of simulating variation)

6. **Write persona files** under `eval/simulation/personas/<task_id>/` and the trajectory judge prompt(s) under `eval/simulation/judge/`.

## Rules

- Skip this skill entirely for agents with no multi-turn/stateful tasks — do not force personas onto single-turn tasks.
- Simulator model family must differ from both SUT and judge — check this explicitly before finalizing config, don't default to "whatever's configured."
- Success conditions must be machine-checkable — if the user proposes a subjective one, push back and ask them to make it checkable or move it into the trajectory judge criteria instead.
- Pause for persona review before writing files.
