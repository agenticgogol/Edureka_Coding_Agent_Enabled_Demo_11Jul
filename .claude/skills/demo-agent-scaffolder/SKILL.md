---
name: demo-agent-scaffolder
description: MUST USE when the user wants a toy/practice agent to run the eval toolkit against — "give me a demo agent", "scaffold a practice agent", "I need something to eval for learning/teaching", "demo_agent/". Mode A of this toolkit — builds an intentionally imperfect agent for teaching failure-analyzer, not a production agent. Trigger eagerly on any mention of a demo, sample, or practice agent to test the eval skills on.
---

# Demo Agent Scaffolder

Scaffolds a toy agent under `demo_agent/` — deliberately imperfect, so the rest of the eval toolkit (especially failure-analyzer) has real signal to work with.

## Steps

1. **Pick an archetype with the user** (ask if not specified): support, RAG, classifier, or tool-using.

2. **Scaffold `demo_agent/`** with, appropriate to the archetype:
   - fake/synthetic data (a small local dataset — no real user data, no external calls to real services)
   - 2-4 fake tools (stubbed functions simulating real tool behavior, e.g. `lookup_order(id)`, `issue_refund(id, amount)`, returning canned/synthetic responses)
   - a starter system prompt defining the agent's role and instructions

3. **Deliberately seed 2-3 known bugs.** Pick these from realistic failure patterns matching the categories failure-analyzer looks for — e.g.:
   - a policy the system prompt states but the agent doesn't consistently enforce
   - a multi-intent scenario where the prompt doesn't instruct the agent to address every sub-request, so it drops one
   - a tool-call bug (wrong argument mapping, or a missing check before calling a destructive tool)
   - vague deferral language that sounds like a wide fix but leaves the agent under-committing to an answer

   Pick bugs that are subtle enough to require a real eval run to surface — not something a smoke test would catch instantly.

4. **Log the seeded bugs in `eval/state.md`** under a clearly marked `## Seeded Bugs (instructor notes)` section: what the bug is, where it lives in the code, and which failure-analyzer category it should surface under. This is instructor-facing documentation, not something the agent under test should ever see or that gets surfaced to a student running the eval blind.

## Rules

- This produces a deliberately flawed agent for teaching purposes — do not "fix" the seeded bugs as part of scaffolding, and do not silently make the agent too obviously broken (bugs should require an actual eval run to catch, not be visible on a glance at the prompt).
- Seeded bugs must map cleanly to failure-analyzer's existing categories so the downstream skill has something coherent to cluster.
- Keep `eval/state.md`'s instructor notes clearly separated from anything a student/grader would read as ground truth about the agent's intended behavior.
- No real external calls, no real user data — everything here is synthetic and local.
