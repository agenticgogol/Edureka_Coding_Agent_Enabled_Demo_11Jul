"""Appends one MetricsHistoryRecord row to evals/results/metrics_history.jsonl
and regenerates evals/results/dashboard.html.

Called by judge-align-new (after step d/e writes metrics.json) and by
eval-ci-new's check_regression.py (after each CI run) — never call
evallib.jsonl.append_jsonl directly from those scripts; go through this one
so the dashboard regenerates every time a row is added, in one place.

Usage (calibration run):
    python evals/scripts/append_metrics_history.py \\
        --run-type calibration --failure-mode-id <id> --method judge \\
        --tpr 1.0 --tnr 1.0 --p-observed 0.15 --theta-hat 0.15 \\
        --ci-low 0.15 --ci-high 0.15 --n-test 8 --judge-model-id gpt-4o-2024-08-06

Usage (CI run):
    python evals/scripts/append_metrics_history.py \\
        --run-type ci --failure-mode-id <id> --method code \\
        --ci-rate 0.125 --baseline-rate 0.15 --regression-status ok --n-golden 8
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent.parent))

from evallib.jsonl import append_jsonl  # noqa: E402
from evallib.schema import MetricsHistoryRecord  # noqa: E402

HISTORY_PATH = PROJECT_ROOT / "evals" / "results" / "metrics_history.jsonl"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-type", required=True, choices=["calibration", "ci"])
    p.add_argument("--failure-mode-id", required=True)
    p.add_argument("--method", required=True, choices=["code", "judge"])
    # calibration fields
    p.add_argument("--tpr", type=float)
    p.add_argument("--tnr", type=float)
    p.add_argument("--p-observed", type=float)
    p.add_argument("--theta-hat", type=float)
    p.add_argument("--ci-low", type=float)
    p.add_argument("--ci-high", type=float)
    p.add_argument("--n-test", type=int)
    p.add_argument("--judge-model-id")
    # ci fields
    p.add_argument("--ci-rate", type=float)
    p.add_argument("--baseline-rate", type=float)
    p.add_argument("--regression-status", choices=["ok", "regressed", "no_baseline", "skipped_uncalibrated"])
    p.add_argument("--n-golden", type=int)
    p.add_argument("--notes", default="")
    args = p.parse_args()

    timestamp = datetime.now(timezone.utc).isoformat()
    record = MetricsHistoryRecord(
        run_id=f"{timestamp}-{args.failure_mode_id}-{args.run_type}-{uuid.uuid4().hex[:8]}",
        timestamp=timestamp,
        run_type=args.run_type,
        failure_mode_id=args.failure_mode_id,
        method=args.method,
        tpr=args.tpr,
        tnr=args.tnr,
        p_observed=args.p_observed,
        theta_hat=args.theta_hat,
        ci_low=args.ci_low,
        ci_high=args.ci_high,
        n_test=args.n_test,
        judge_model_id=args.judge_model_id,
        ci_rate=args.ci_rate,
        baseline_rate=args.baseline_rate,
        regression_status=args.regression_status,
        n_golden=args.n_golden,
        notes=args.notes,
    )
    append_jsonl(record, HISTORY_PATH)
    print(f"appended {record.run_id} to {HISTORY_PATH}")

    # Regenerate the dashboard immediately so it's never stale. render_dashboard.py
    # is a sibling of this script in evals/scripts/ once both are copied into a project.
    render_script = Path(__file__).resolve().parent / "render_dashboard.py"
    if render_script.exists():
        import runpy
        runpy.run_path(str(render_script), run_name="__main__")
    else:
        print(f"WARNING: render_dashboard.py not found — dashboard.html not regenerated. "
              f"Run /eval-dashboard-new to set it up.")


if __name__ == "__main__":
    main()
