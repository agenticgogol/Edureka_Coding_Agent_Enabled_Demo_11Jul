#!/usr/bin/env python3
"""PreToolUse hook: deny reads/edits of the locked test split unless
EVAL_FINAL_VALIDATION=1 is set for that call.

This is hook H1 from the eval-suite design (.claude/EVAL_SUITE_DESIGN.md).
Copied by eval-ci-new to .claude/hooks/lock_test_split.py. Wired in
settings.json against Read|Edit|Write|Bash|Grep|Glob (see
eval-ci-new/SKILL.md for the exact matcher) — this script does the
path-matching itself rather than relying on `if` permission-rule syntax,
because that syntax doesn't generalize across six different tools reading
one path the same way.

Guards any path containing "test.jsonl" under evals/labels/ — this covers
both a single canonical evals/labels/test.jsonl (written by eval-ci-new's
golden-set promotion step) and any per-failure-mode file whose name happens
to include "test". It intentionally does NOT try to parse JSONL content to
find split=="test" rows inside a combined file — that's too slow and fragile
for a PreToolUse hook to do on every tool call; keep test-split rows in a
physically separate, name-matched file instead.
"""

from __future__ import annotations

import json
import os
import re
import sys

GUARDED_PATTERN = re.compile(r"evals/labels/[^/\s]*test[^/\s]*\.jsonl")


def extract_candidate_strings(tool_input: dict) -> list[str]:
    """Pull every string value out of tool_input that could contain a path
    (file_path, path, command, pattern, ...) — cheap and over-inclusive by
    design; false positives just mean an extra deny, which is safe here."""
    strings: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(tool_input)
    return strings


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {}) or {}

    candidates = extract_candidate_strings(tool_input)
    touches_test_split = any(GUARDED_PATTERN.search(s) for s in candidates)

    if not touches_test_split:
        # Not our concern; allow silently.
        return 0

    if os.environ.get("EVAL_FINAL_VALIDATION") == "1":
        # Explicit, single, confirmed final-validation read/write — allow.
        return 0

    decision = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Denied: this tool call touches the locked test split "
                "(evals/labels/*test*.jsonl). Reading or editing the test "
                "split during judge iteration invalidates any TPR/TNR "
                "computed from it — there is no statistical fix afterward, "
                "only a fresh stratified_split with a new seed. If this is "
                "the single, user-confirmed final-validation read "
                "(judge-align-new step d), set EVAL_FINAL_VALIDATION=1 for "
                "that call only."
            ),
        }
    }
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
