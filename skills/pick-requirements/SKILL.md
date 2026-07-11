---
name: pick-requirements
description: Use when a plan.md step calls for locking dependencies. Decides and pins requirements.txt (Python) and/or package.json (Node) from design.md's tech choices.
---

# Pick Requirements

## When to use

- After `design.md` is approved, before component-building skills run, so
  every skill builds against a known dependency set.
- Also re-run (narrowly) if a later step needs a dependency design.md
  didn't anticipate — update the file, don't leave undeclared imports.

## Procedure

1. From `design.md`'s "Tech choices" section, list every library actually
   needed — no speculative additions ("might need this later").
2. Python: write `requirements.txt` (or `backend/requirements.txt` if the
   project splits frontend/backend) with pinned major versions
   (`fastapi>=0.110,<1.0`), not unpinned bare names.
3. Node: write/update `package.json` dependencies the same way.
4. Cross-check with `integrate-and-assemble` responsibilities later — if
   frontend and backend both need overlapping tooling (e.g. a shared type
   or schema library), note it here so integration doesn't hit a version
   mismatch.
5. Prefer the lightest dependency that satisfies the design — don't add a
   framework because it's popular if a stdlib/simple alternative covers the
   brief.
