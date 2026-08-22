"""CI gate: compares evals/results/ci_run_latest.json (this run) against
evals/results/metrics.json (the calibrated baseline theta_hat per
failure_mode_id, from judge-align-new step e) and exits non-zero if any
failure mode's pass rate has dropped by more than --threshold.

A failure_mode_id with no metrics.json entry (a code eval — those aren't
bias-corrected/calibrated the way judges are, or a judge that hasn't
finished calibration yet) has no established baseline to regress against;
its row is printed as informational only and never fails the gate on its
own. This keeps the table honest about what is/isn't actually being
enforced, rather than silently treating "no baseline" as "passing."
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CI_RUN_PATH = PROJECT_ROOT / "evals" / "results" / "ci_run_latest.json"
METRICS_PATH = PROJECT_ROOT / "evals" / "results" / "metrics.json"
APPEND_HISTORY_SCRIPT = PROJECT_ROOT / "evals" / "scripts" / "append_metrics_history.py"

_STATUS_MAP = {
    "ok": "ok",
    "REGRESSED": "regressed",
    "no baseline yet": "no_baseline",
    "SKIPPED (uncalibrated judge)": "skipped_uncalibrated",
}


def _append_history_row(fmid: str, method: str, status: str, current_rate: float | None,
                         baseline_rate: float | None, n_golden: int | None) -> None:
    if not APPEND_HISTORY_SCRIPT.exists():
        return  # eval-dashboard-new not set up yet for this project; skip silently, not fatal to the gate
    cmd = [
        sys.executable, str(APPEND_HISTORY_SCRIPT),
        "--run-type", "ci", "--failure-mode-id", fmid, "--method", method,
        "--regression-status", _STATUS_MAP[status],
    ]
    if current_rate is not None:
        cmd += ["--ci-rate", str(current_rate)]
    if baseline_rate is not None:
        cmd += ["--baseline-rate", str(baseline_rate)]
    if n_golden is not None:
        cmd += ["--n-golden", str(n_golden)]
    subprocess.run(cmd, check=False)


def _this_run_positive_rate(entry: dict) -> float | None:
    """The rate this CI run measured for a failure mode: for a code eval,
    the fraction of golden-set traces that FAILED the check (pass_rate is
    the fraction that passed, so 1 - pass_rate is the failure/positive
    rate, matching theta_hat's polarity — theta_hat estimates the true rate
    of the failure mode occurring, not the rate of it being absent). For a
    judge, p_observed already is the positive (failure) rate directly."""
    if entry.get("skipped"):
        return None
    if entry["method"] == "code":
        pass_rate = entry.get("pass_rate")
        return None if pass_rate is None else 1 - pass_rate
    return entry.get("p_observed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.05)
    args = parser.parse_args()

    ci_run = json.loads(CI_RUN_PATH.read_text())
    metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else []
    metrics_by_id = {m["failure_mode_id"]: m for m in metrics}

    rows = []
    any_regression = False

    for fmid, entry in ci_run.items():
        current_rate = _this_run_positive_rate(entry)
        baseline = metrics_by_id.get(fmid)
        method = entry.get("method", "code")
        n_golden = entry.get("n")

        if entry.get("skipped"):
            rows.append((fmid, "SKIPPED (uncalibrated judge)", "-", "-", "-"))
            _append_history_row(fmid, method, "SKIPPED (uncalibrated judge)", current_rate, None, n_golden)
            continue

        if baseline is None:
            rows.append((fmid, "no baseline yet", "-", f"{current_rate:.3f}" if current_rate is not None else "-", "-"))
            _append_history_row(fmid, method, "no baseline yet", current_rate, None, n_golden)
            continue

        baseline_rate = baseline["theta_hat"]
        drop = current_rate - baseline_rate  # positive = failure rate got WORSE (higher)
        regressed = drop > args.threshold
        any_regression = any_regression or regressed
        status = "REGRESSED" if regressed else "ok"
        rows.append((fmid, status, f"{baseline_rate:.3f}", f"{current_rate:.3f}", f"{drop:+.3f}"))
        _append_history_row(fmid, method, status, current_rate, baseline_rate, n_golden)

    print(f"{'failure_mode_id':<38} {'status':<26} {'baseline':<10} {'current':<10} {'delta':<8}")
    print("-" * 96)
    for fmid, status, baseline_str, current_str, delta_str in rows:
        print(f"{fmid:<38} {status:<26} {baseline_str:<10} {current_str:<10} {delta_str:<8}")

    if any_regression:
        print(f"\nFAIL: at least one failure mode's rate rose by more than {args.threshold:.3f} vs. baseline.")
        sys.exit(1)
    print("\nOK: no regression beyond threshold on any calibrated failure mode.")


if __name__ == "__main__":
    main()
