---
description: Report which pipeline stages an existing project/concept has actually completed, cross-checked against the filesystem — not just plan.md's checkboxes.
argument-hint: <projects|concepts> <slug>
---

Parse `$ARGUMENTS` as `<kind> <slug>` (kind is `projects` or `concepts`).

Report, stage by stage, per the `WORKFLOW.md` sequence table:

1. Brief exists? (`$1/$2/project_brief.md` or `concept_brief.md`)
2. Design exists? (`design.md`)
3. Tests drafted and user-confirmed? (check `plan.md`/`design.md` for a
   recorded confirmation, not just the tests file existing)
4. Plan exists and references `run-tests`, `integrate-and-assemble`,
   `run-and-verify`?
5. Component code present? (`frontend/`, `backend/`, `notebook.ipynb`)
6. Tests actually passing right now? Don't trust `plan.md`'s checkbox —
   actually run `run-tests` (or delegate to `/test-project $ARGUMENTS`) and
   report the real current result, since code may have changed since the
   checkbox was ticked.
7. `security-check` / `eval-and-observability` done, if applicable?
8. `lint-and-typecheck` / `validate-env` done?
9. `integrate-and-assemble` done — single run command exists?
10. `run-and-verify` last passed when? Re-run if state looks stale.
11. `reviewer` pass done?
12. Deploy config present, if the brief required it?

Summarize as a short checklist (done / not done / stale-needs-recheck) and
recommend the next command to run (`/run-pipeline`, `/test-project`, or a
specific skill).
