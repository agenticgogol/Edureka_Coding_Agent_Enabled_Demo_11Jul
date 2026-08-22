"""Runs an LLM judge prompt over a set of traces, with a
(trace_id, sha256(prompt), model_id) result cache under
evals/.cache/judge_results/ so re-running after a small prompt edit doesn't
re-bill unchanged traces.

Usage:
    python evals/scripts/run_judge.py --judge evals/judges/<id>.md \
        --failure-mode-id <id> --split dev --estimate

    python evals/scripts/run_judge.py --judge evals/judges/<id>.md \
        --failure-mode-id <id> --split dev

    python evals/scripts/run_judge.py --judge evals/judges/<id>.md \
        --failure-mode-id <id> --split test   # requires EVAL_FINAL_VALIDATION=1

    python evals/scripts/run_judge.py --judge evals/judges/<id>.md \
        --failure-mode-id <id> --population all   # for step (e)

Prints aggregate JSON: {"results": {trace_id: bool, ...}, "critiques": {...},
"n_cached": N, "n_called": M, "estimated_cost_usd": X}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT.parent.parent / ".env")

from evallib.jsonl import read_jsonl  # noqa: E402
from evallib.schema import Trace  # noqa: E402

CACHE_DIR = PROJECT_ROOT / "evals" / ".cache" / "judge_results"
MODEL_ID = os.environ.get("JUDGE_MODEL_ID", "gpt-4o-mini")
# Pricing (USD per 1K tokens).
_PRICING = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-2024-08-06": (0.0025, 0.01),
}
PRICE_PER_1K_INPUT, PRICE_PER_1K_OUTPUT = _PRICING.get(MODEL_ID, (0.00015, 0.0006))
EST_INPUT_TOKENS_PER_CALL = 1200  # judge prompt + trace, rough estimate
EST_OUTPUT_TOKENS_PER_CALL = 150  # critique + label line


def _trace_text(trace: Trace) -> str:
    lines = [f"query_id: {trace.query_id}", f"dimension_tuple: {trace.dimension_tuple}", "", "Turns:"]
    for i, turn in enumerate(trace.turns):
        lines.append(f"[{i}] {turn.role.value}: {turn.content}")
    lines.append("")
    lines.append(f"final_response: {trace.final_response}")
    raw = trace.metadata.get("raw_result")
    if raw:
        lines.append("")
        lines.append(f"raw_result (structured fields): {json.dumps(raw, default=str)}")
    return "\n".join(lines)


def _cache_key(trace_id: str, prompt_hash: str, model_id: str) -> Path:
    key = f"{trace_id}__{prompt_hash}__{model_id}.json"
    return CACHE_DIR / key


def _parse_label(response_text: str) -> tuple[bool, str]:
    match = re.search(r"LABEL:\s*(PASS|FAIL)\s*$", response_text.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"could not parse LABEL: PASS|FAIL from judge response: {response_text!r}")
    label = match.group(1).upper()
    critique = response_text[: match.start()].strip()
    return (label == "FAIL"), critique


def run(judge_prompt: str, failure_mode_id: str, traces: list[Trace], estimate: bool) -> dict[str, Any]:
    prompt_hash = hashlib.sha256(judge_prompt.encode()).hexdigest()[:16]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    to_call: list[Trace] = []
    cached_results: dict[str, dict[str, Any]] = {}
    for trace in traces:
        cache_path = _cache_key(trace.query_id, prompt_hash, MODEL_ID)
        if cache_path.exists():
            cached_results[trace.query_id] = json.loads(cache_path.read_text())
        else:
            to_call.append(trace)

    if estimate:
        n_new = len(to_call)
        est_cost = n_new * (
            EST_INPUT_TOKENS_PER_CALL / 1000 * PRICE_PER_1K_INPUT
            + EST_OUTPUT_TOKENS_PER_CALL / 1000 * PRICE_PER_1K_OUTPUT
        )
        return {
            "estimate": True,
            "n_total": len(traces),
            "n_cached": len(cached_results),
            "n_new_calls": n_new,
            "estimated_cost_usd": round(est_cost, 4),
        }

    if to_call:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        for trace in to_call:
            full_prompt = f"{judge_prompt}\n\n## Trace to evaluate\n\n{_trace_text(trace)}"
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0,
            )
            text = response.choices[0].message.content or ""
            judge_label, critique = _parse_label(text)
            result = {"judge_label": judge_label, "critique": critique}
            cache_path = _cache_key(trace.query_id, prompt_hash, MODEL_ID)
            cache_path.write_text(json.dumps(result))
            cached_results[trace.query_id] = result

    return {
        "estimate": False,
        "failure_mode_id": failure_mode_id,
        "results": {qid: r["judge_label"] for qid, r in cached_results.items()},
        "critiques": {qid: r["critique"] for qid, r in cached_results.items()},
        "n_cached": len(traces) - len(to_call),
        "n_called": len(to_call),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", required=True, type=Path)
    parser.add_argument("--failure-mode-id", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--split", choices=["train", "dev", "test"])
    group.add_argument("--population", choices=["all"])
    parser.add_argument("--estimate", action="store_true")
    args = parser.parse_args()

    judge_prompt = args.judge.read_text()
    traces_by_id = {t.query_id: t for t in read_jsonl(Trace, PROJECT_ROOT / "evals" / "traces.jsonl")}

    if args.split:
        if args.split == "test" and os.environ.get("EVAL_FINAL_VALIDATION") != "1":
            print(
                json.dumps(
                    {"error": "test split read requires EVAL_FINAL_VALIDATION=1 (see judge-align-new step d)"}
                )
            )
            sys.exit(1)
        splits_path = PROJECT_ROOT / "evals" / "labels" / f"{args.failure_mode_id}_splits.json"
        splits = json.loads(splits_path.read_text())
        trace_ids = splits[args.split]
    else:
        trace_ids = list(traces_by_id.keys())

    traces = [traces_by_id[tid] for tid in trace_ids]
    result = run(judge_prompt, args.failure_mode_id, traces, estimate=args.estimate)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
