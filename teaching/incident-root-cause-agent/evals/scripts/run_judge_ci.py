"""CI entrypoint: runs every routed evaluator (code + judge) from
evals/evaluators/routing.yaml over evals/golden/golden_set.jsonl and writes
evals/results/ci_run_latest.json.

- `method: code` entries: import the check_<failure_mode_id> function from
  evals/evaluators/<failure_mode_id>.py and call it directly (a pure
  function over Trace, no API cost).
- `method: judge` entries: only run if evals/results/metrics.json already
  has a MetricsRecord for that failure_mode_id (i.e. it passed
  judge-align-new calibration) — an uncalibrated judge is not safe to gate
  on, matching hook H4's rule. Otherwise print a warning and skip it,
  recording that skip in the output file so check_regression.py doesn't
  silently treat a missing judge as passing.

Reuses run_judge.py's exact judge-calling code (same cache, same model,
same prompt-parsing) rather than a second implementation.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent.parent))

import yaml  # noqa: E402

from evallib.jsonl import read_jsonl  # noqa: E402
from evallib.schema import Trace  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_judge  # noqa: E402  (reuse its run()/judge-calling code, not a second implementation)

ROUTING_PATH = PROJECT_ROOT / "evals" / "evaluators" / "routing.yaml"
METRICS_PATH = PROJECT_ROOT / "evals" / "results" / "metrics.json"
GOLDEN_PATH = PROJECT_ROOT / "evals" / "golden" / "golden_set.jsonl"
OUT_PATH = PROJECT_ROOT / "evals" / "results" / "ci_run_latest.json"


def _load_code_check(failure_mode_id: str):
    module_path = PROJECT_ROOT / "evals" / "evaluators" / f"{failure_mode_id}.py"
    spec = importlib.util.spec_from_file_location(failure_mode_id.replace("-", "_"), module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn_name = f"check_{failure_mode_id.replace('-', '_')}"
    return getattr(module, fn_name)


def main() -> None:
    routing = yaml.safe_load(ROUTING_PATH.read_text())
    metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else []
    metrics_by_id = {m["failure_mode_id"]: m for m in metrics}

    golden_traces = list(read_jsonl(Trace, GOLDEN_PATH))

    output: dict[str, dict] = {}

    for entry in routing:
        fmid = entry["failure_mode_id"]
        if entry["method"] == "code":
            check_fn = _load_code_check(fmid)
            per_trace = {t.query_id: check_fn(t) for t in golden_traces}
            n_fail = sum(1 for passed in per_trace.values() if not passed)
            output[fmid] = {
                "method": "code",
                "per_trace_pass": per_trace,
                "pass_rate": 1 - (n_fail / len(per_trace)) if per_trace else None,
                "n": len(per_trace),
            }
        elif entry["method"] == "judge":
            if fmid not in metrics_by_id:
                print(f"WARNING: skipping judge '{fmid}' — no calibration record in {METRICS_PATH} "
                      f"(judge-align-new has not validated it yet). Not gating on it.")
                output[fmid] = {"method": "judge", "skipped": True, "reason": "uncalibrated"}
                continue
            judge_prompt = (PROJECT_ROOT / "evals" / "judges" / f"{fmid}.md").read_text()
            result = run_judge.run(judge_prompt, fmid, golden_traces, estimate=False)
            per_trace = result["results"]
            n_positive = sum(1 for v in per_trace.values() if v)
            output[fmid] = {
                "method": "judge",
                "per_trace_judge_label": per_trace,
                "p_observed": n_positive / len(per_trace) if per_trace else None,
                "n": len(per_trace),
                "n_cached": result["n_cached"],
                "n_called": result["n_called"],
            }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
