---
name: golden-dataset-csv-sync
description: Use when the user wants to hand-edit eval/golden_set.jsonl in a spreadsheet — "export the golden set to CSV/Excel", "let me edit the golden set in Sheets", "sync my CSV edits back to golden_set.jsonl". Exports golden_set.jsonl to a CSV (opens directly in Excel/Sheets/Numbers, no extra dependency needed) and re-imports a manually-edited CSV back into golden_set.jsonl, validating and backing up before overwriting.
---

# Golden Dataset CSV Sync

Round-trips `eval/golden_set.jsonl` through a CSV file so the user can review/edit examples in a spreadsheet instead of raw JSONL, then bring their edits back in.

Uses plain CSV (not `.xlsx`) so it works with Python's stdlib only — no `openpyxl`/`pandas` dependency required. CSV opens natively in Excel, Google Sheets, and Numbers, so this covers the "Excel" case without adding a dependency.

## Export: JSONL → CSV

1. Locate the target `golden_set.jsonl` (ask the user which project/eval folder if ambiguous — e.g. `projects/<slug>/eval/golden_set.jsonl`).
2. Run:
   ```bash
   python3 .claude/skills/golden-dataset-csv-sync/scripts/golden_to_csv.py <path/to/golden_set.jsonl>
   ```
   This writes `golden_set.csv` next to the `.jsonl` (or pass an explicit output path as a second argument).
3. Tell the user: the `input` and `metrics_applicable` columns are JSON-encoded in their cells (since they're nested/list values) — when editing in Excel/Sheets, they must keep those cells valid JSON text (e.g. `{"user_message": "...", "context": "..."}` or `["classification accuracy"]`). Editing `id`, `task_id`, `category`, `good_output_notes`, `bad_output_notes`, `source` is plain text, no special care needed.
4. Point the user at the file path so they can open/edit it, then stop — do not proceed to re-import until they say they're done editing.

## Import: CSV → JSONL (after the user has made manual changes)

1. Confirm with the user which CSV file has their edits and which `golden_set.jsonl` it should sync back into (normally the same pair used for export).
2. Run:
   ```bash
   python3 .claude/skills/golden-dataset-csv-sync/scripts/csv_to_golden.py <path/to/golden_set.csv> <path/to/golden_set.jsonl>
   ```
3. The script:
   - Validates every row: required columns present, `input`/`metrics_applicable` cells are valid JSON, `category` is one of `common`/`edge`/`past_failure`, `id` is non-empty. If any row fails validation, it prints all errors and writes nothing — report these back to the user for fixing in the CSV, then re-run.
   - On success, backs up the existing `golden_set.jsonl` to `golden_set.jsonl.bak` before overwriting.
   - Prints added / removed / modified example IDs — relay this diff to the user as a summary of what changed, rather than just saying "done."
4. After a successful import, remind the user the golden set changed and later pipeline steps (grader-selector, judge-prompt-builder, baseline-runner) may need re-running if example content shifted materially — don't re-run them automatically, just flag it.

## Rules

- Never invent or drop fields — the CSV schema mirrors the golden-dataset-builder line schema exactly: `id, task_id, category, input, good_output_notes, bad_output_notes, metrics_applicable, source`.
- Never silently overwrite `golden_set.jsonl` without the `.bak` backup step.
- Never proceed past export to import in the same turn unless the user has actually confirmed they made their edits — this is a two-step, user-in-the-loop workflow, not an automatic round-trip.
- If validation fails on import, do not attempt to auto-fix the CSV yourself — surface the exact errors and let the user (or a follow-up edit) correct them.
