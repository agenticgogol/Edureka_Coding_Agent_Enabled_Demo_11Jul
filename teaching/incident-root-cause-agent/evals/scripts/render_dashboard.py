"""Regenerates evals/results/dashboard.html from evals/results/metrics_history.jsonl.

Self-contained (no CDN, no external JS/CSS) so it opens directly from the
file system. Copied verbatim into a project by eval-dashboard-new — this
file itself is not meant to be hand-edited per project; extend the schema
in evallib/schema.py's MetricsHistoryRecord instead if a new field is
needed, and this renderer will pick it up via its **row.model_dump()**
table columns (the table always shows every field, so a new field appears
there automatically; only the charts need code changes for new fields).

Usage: python evals/scripts/render_dashboard.py
       (reads evals/results/metrics_history.jsonl, writes evals/results/dashboard.html,
        both resolved relative to this script's project root — see PROJECT_ROOT below)
"""
from __future__ import annotations

import html
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent.parent))  # monorepo evallib fallback

from evallib.jsonl import read_jsonl  # noqa: E402
from evallib.schema import MetricsHistoryRecord  # noqa: E402

HISTORY_PATH = PROJECT_ROOT / "evals" / "results" / "metrics_history.jsonl"
OUT_PATH = PROJECT_ROOT / "evals" / "results" / "dashboard.html"

# --- palette tokens (dataviz skill's validated reference palette) ----------
SERIES_1_LIGHT, SERIES_1_DARK = "#2a78d6", "#3987e5"  # blue — theta_hat / ci_rate
SERIES_2_LIGHT, SERIES_2_DARK = "#eb6834", "#d95926"  # orange — tpr/tnr secondary, baseline_rate
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
STATUS_WARNING = "#fab219"
BAND_LIGHT, BAND_DARK = "#cde2fb", "#184f95"  # sequential step 100 / 600 — CI band fill


def _fmt(v: float | None, digits: int = 3) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def _svg_line_chart(
    *,
    width: int = 640,
    height: int = 200,
    series: list[tuple[str, list[float | None], str]],  # (label, values, color-var)
    band: tuple[list[float | None], list[float | None]] | None = None,  # (low, high) same length
    x_labels: list[str],
    y_min: float = 0.0,
    y_max: float = 1.0,
    status_colors: list[str] | None = None,  # per-x-point color override for the first series' markers
) -> str:
    pad_l, pad_r, pad_t, pad_b = 44, 16, 16, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(x_labels)

    def x_at(i: int) -> float:
        return pad_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def y_at(v: float) -> float:
        v = max(y_min, min(y_max, v))
        return pad_t + plot_h * (1 - (v - y_min) / (y_max - y_min))

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="line chart" class="chart-svg">'
    ]

    # gridlines + y ticks
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + plot_h * (1 - frac)
        val = y_min + frac * (y_max - y_min)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" class="gridline"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{y + 3:.1f}" class="tick" text-anchor="end">{val:.2f}</text>')

    # x labels (first, middle, last — avoid overcrowding)
    label_idxs = sorted(set([0, n // 2, n - 1])) if n > 0 else []
    for i in label_idxs:
        parts.append(
            f'<text x="{x_at(i):.1f}" y="{height - 6}" class="tick" text-anchor="middle">'
            f'{html.escape(x_labels[i])}</text>'
        )

    # CI band (first series only, if provided)
    if band is not None:
        low, high = band
        pts_top = [(x_at(i), y_at(v)) for i, v in enumerate(high) if v is not None]
        pts_bot = [(x_at(i), y_at(v)) for i, v in enumerate(low) if v is not None][::-1]
        if pts_top and pts_bot:
            path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts_top + pts_bot) + " Z"
            parts.append(f'<path d="{path}" class="ci-band"/>')

    for series_i, (label, values, color_var) in enumerate(series):
        pts = [(x_at(i), y_at(v)) for i, v in enumerate(values) if v is not None]
        if pts:
            path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            parts.append(f'<path d="{path}" fill="none" class="series-line" style="stroke:var({color_var})"/>')
        for i, v in enumerate(values):
            if v is None:
                continue
            marker_color = (
                f"var({color_var})"
                if series_i > 0 or not status_colors or status_colors[i] is None
                else status_colors[i]
            )
            parts.append(
                f'<circle cx="{x_at(i):.1f}" cy="{y_at(v):.1f}" r="4" style="fill:{marker_color}">'
                f'<title>{html.escape(label)} @ {html.escape(x_labels[i])}: {v:.3f}</title></circle>'
            )

    parts.append("</svg>")
    return "".join(parts)


# One-line explanation per column, shown as a hover tooltip on every table
# header AND spelled out in full in the glossary section (Step: don't rely
# on hover alone — a static file's tooltips are easy to miss).
COLUMN_GLOSSARY: dict[str, str] = {
    "timestamp": "When this run happened (UTC).",
    "run_type": "\"calibration\" = a judge-align-new accuracy check against human labels. \"ci\" = a CI gate run re-scoring the golden set.",
    "method": "\"code\" = a deterministic pass/fail function, always exact. \"judge\" = an LLM judge, which needs calibration before its numbers can be trusted.",
    "tpr": "True Positive Rate (sensitivity): of traces a human confirmed DO have this failure, the fraction the judge also caught. 1.0 = never misses a real failure.",
    "tnr": "True Negative Rate (specificity): of traces a human confirmed do NOT have this failure, the fraction the judge correctly passed. 1.0 = never false-alarms.",
    "p_observed": "The raw fraction of traces the judge flagged as failing on this run's population — NOT corrected for the judge's own error rate.",
    "theta_hat": "The bias-corrected estimate of the TRUE failure rate, after accounting for TPR/TNR. This is the trustworthy number — read this, not p_observed.",
    "ci_low": "Lower bound of the 95% confidence interval around theta_hat.",
    "ci_high": "Upper bound of the 95% confidence interval around theta_hat. A wide ci_low-ci_high gap means too little test data to be confident.",
    "n_test": "How many held-out test-split traces this calibration was measured on. Small n means treat TPR/TNR/theta_hat with caution.",
    "judge_model_id": "Exact model snapshot the judge ran as for this calibration — CI must use this same model, or the calibration doesn't apply to what's actually running.",
    "ci_rate": "The failure rate THIS CI run measured on the current golden set (like p_observed, but from a production check, not calibration).",
    "baseline_rate": "The calibrated theta_hat this run's ci_rate was compared against.",
    "regression_status": "\"ok\" = within threshold of baseline. \"regressed\" = failure rate rose too much — investigate. \"no_baseline\" = no calibration exists yet (normal for code evals). \"skipped_uncalibrated\" = a judge was skipped because it isn't calibrated yet.",
    "n_golden": "How many golden-set traces this CI run scored against.",
    "notes": "Free-text context for this row (e.g. marks a backfilled historical run).",
}


def _glossary_html() -> str:
    rows = "".join(
        f"<tr><td><code>{html.escape(col)}</code></td><td>{html.escape(desc)}</td></tr>"
        for col, desc in COLUMN_GLOSSARY.items()
    )
    return f"""
<details class="glossary">
  <summary>What do these numbers mean? (click to expand)</summary>
  <p class="muted">
    Each failure mode below is either a <strong>code eval</strong> (a deterministic
    function — always exact, no calibration needed) or a <strong>judge</strong>
    (an LLM scoring traces — its own accuracy must be calibrated against real
    human labels before its numbers mean anything). A <strong>calibration</strong>
    run measures a judge's TPR/TNR and produces <code>theta_hat</code>, the
    trustworthy bias-corrected failure-rate estimate. A <strong>CI</strong> run
    re-scores the current golden set and compares it against that calibrated
    baseline to catch drift.
  </p>
  <table class="glossary-table"><thead><tr><th>Column</th><th>Meaning</th></tr></thead>
  <tbody>{rows}</tbody></table>
</details>
"""


def _table(rows: list[MetricsHistoryRecord]) -> str:
    if not rows:
        return "<p class=\"muted\">No runs recorded yet.</p>"
    all_cols = [
        "timestamp", "run_type", "method", "tpr", "tnr", "p_observed", "theta_hat",
        "ci_low", "ci_high", "n_test", "judge_model_id", "ci_rate", "baseline_rate",
        "regression_status", "n_golden", "notes",
    ]
    always_shown = {"timestamp", "run_type", "method", "notes"}
    dumps = [r.model_dump() for r in rows]
    # Only show a column if at least one row in THIS failure mode's history has
    # a real value for it — a code eval's rows never populate tpr/tnr/theta_hat
    # etc. (those are calibration-only), and showing a wall of "—" for columns
    # that structurally never apply here reads as broken rather than N/A.
    cols = [c for c in all_cols if c in always_shown or any(d[c] is not None for d in dumps)]
    omitted = [c for c in all_cols if c not in cols]

    head = "".join(
        f'<th title="{html.escape(COLUMN_GLOSSARY.get(c, ""))}">{c}</th>' for c in cols
    )
    body_rows = []
    for d, r in sorted(zip(dumps, rows), key=lambda pair: pair[1].timestamp, reverse=True):
        cells = "".join(f"<td>{html.escape(str(d[c]) if d[c] is not None else '—')}</td>" for c in cols)
        status_class = f' class="row-{r.regression_status}"' if r.regression_status else ""
        body_rows.append(f"<tr{status_class}>{cells}</tr>")

    note = ""
    if omitted:
        note = (
            f'<p class="chart-note">Columns hidden here because no run of this failure mode '
            f'has ever populated them: <code>{"</code>, <code>".join(omitted)}</code> — these are '
            f'calibration-only fields, and this failure mode has no calibration runs '
            f'(normal for a <strong>code</strong> eval, which needs no calibration).</p>'
        )

    return (
        note
        + '<div class="table-wrap"><table><thead><tr>' + head + "</tr></thead><tbody>"
        + "".join(body_rows) + "</tbody></table></div>"
    )


def render(history: list[MetricsHistoryRecord]) -> str:
    by_mode: dict[str, list[MetricsHistoryRecord]] = {}
    for r in history:
        by_mode.setdefault(r.failure_mode_id, []).append(r)

    sections: list[str] = []
    for fmid in sorted(by_mode):
        rows = sorted(by_mode[fmid], key=lambda r: r.timestamp)
        calib_rows = [r for r in rows if r.run_type == "calibration"]
        ci_rows = [r for r in rows if r.run_type == "ci"]
        method = rows[-1].method

        latest = rows[-1]
        if latest.run_type == "calibration":
            latest_summary = (
                f"true failure rate ≈ {_fmt(latest.theta_hat, 2)} "
                f"(judge catches {_fmt(latest.tpr, 2)} of real failures, "
                f"correctly clears {_fmt(latest.tnr, 2)} of clean traces)"
            )
        elif latest.regression_status == "no_baseline":
            latest_summary = (
                f"measured failure rate {_fmt(latest.ci_rate, 2)} — no calibrated baseline to compare against yet"
            )
        else:
            latest_summary = (
                f"measured failure rate {_fmt(latest.ci_rate, 2)} vs. calibrated baseline "
                f"{_fmt(latest.baseline_rate, 2)} → {latest.regression_status}"
            )

        charts = ""
        if calib_rows:
            x_labels = [r.timestamp[:19] for r in calib_rows]
            theta = [r.theta_hat for r in calib_rows]
            tpr = [r.tpr for r in calib_rows]
            tnr = [r.tnr for r in calib_rows]
            low = [r.ci_low for r in calib_rows]
            high = [r.ci_high for r in calib_rows]
            charts += (
                '<h4>theta_hat: the calibrated true failure rate</h4>'
                '<p class="chart-note">The trustworthy estimate of how often this failure mode really '
                'happens, corrected for the judge\'s own error rate. The shaded band is its 95% '
                'confidence interval — wider means less certain (usually from a small test split); '
                'watch the line for an upward trend across recalibrations.</p>'
                + _svg_line_chart(
                    series=[("theta_hat", theta, "--series-1")],
                    band=(low, high),
                    x_labels=x_labels,
                )
                + '<div class="legend"><span class="dot" style="background:var(--series-1)"></span>theta_hat (true failure rate)'
                + '<span class="dot band-dot"></span>95% confidence interval</div>'
                + '<h4>TPR / TNR: how accurate the judge itself is</h4>'
                + '<p class="chart-note">This is NOT the agent\'s quality — it\'s whether the judge can be '
                'trusted. TPR = fraction of real failures the judge catches; TNR = fraction of clean traces '
                'it correctly passes. Both should stay near 1.0; a drop means the judge prompt or model '
                'needs attention before theta_hat above can be trusted again.</p>'
                + _svg_line_chart(
                    series=[("TPR", tpr, "--series-1"), ("TNR", tnr, "--series-2")],
                    x_labels=x_labels,
                )
                + '<div class="legend"><span class="dot" style="background:var(--series-1)"></span>TPR (catches real failures)'
                + '<span class="dot" style="background:var(--series-2)"></span>TNR (correctly clears clean traces)</div>'
            )
        if ci_rows:
            x_labels = [r.timestamp[:19] for r in ci_rows]
            ci_rate = [r.ci_rate for r in ci_rows]
            baseline = [r.baseline_rate for r in ci_rows]
            has_baseline = any(b is not None for b in baseline)
            all_zero = all(v == 0.0 for v in ci_rate if v is not None)
            status_colors = [
                {"ok": STATUS_GOOD, "regressed": STATUS_CRITICAL}.get(r.regression_status)
                for r in ci_rows
            ]

            zero_note = ""
            if all_zero:
                zero_note = (
                    '<p class="chart-note"><strong>The flat line at 0.00 is a real result, not a '
                    'rendering gap:</strong> this check has found 0 failures across every CI run so far — '
                    'nothing to flag, which is the outcome you want.</p>'
                )
            baseline_note = ""
            if not has_baseline:
                baseline_note = (
                    '<p class="chart-note">No baseline line appears because this failure mode has no '
                    'calibrated comparison point yet (normal for a <strong>code</strong> eval — it needs no '
                    'calibration, so <code>regression_status</code> reads <code>no_baseline</code> for every '
                    'run and nothing here can fail the gate on its own).</p>'
                )

            series = [("measured rate", ci_rate, "--series-1")]
            legend_items = ['<span class="dot" style="background:var(--series-1)"></span>measured rate (this run)']
            if has_baseline:
                series.append(("calibrated baseline", baseline, "--series-2"))
                legend_items.append('<span class="dot" style="background:var(--series-2)"></span>calibrated baseline')
            if any(c is not None for c in status_colors):
                legend_items.append('<span class="dot" style="background:' + STATUS_GOOD + '"></span>ok')
                legend_items.append('<span class="dot" style="background:' + STATUS_CRITICAL + '"></span>regressed')

            charts += (
                '<h4>CI gate: has this failure mode gotten worse since calibration?</h4>'
                '<p class="chart-note">Each CI run re-measures the failure rate on the current golden set '
                '("measured rate") and compares it to the calibrated baseline. '
                '<span style="color:' + STATUS_GOOD + '">Green</span> = within the allowed threshold. '
                '<span style="color:' + STATUS_CRITICAL + '">Red</span> = regressed — the agent is failing '
                'this way more often than when it was calibrated, worth investigating before merging.</p>'
                + zero_note + baseline_note
                + _svg_line_chart(series=series, x_labels=x_labels, status_colors=status_colors)
                + '<div class="legend">' + "".join(legend_items) + '</div>'
            )

        method_note = (
            "deterministic check, always exact — no calibration needed"
            if method == "code"
            else "LLM judge — trust its numbers only once calibrated (see TPR/TNR below)"
        )
        sections.append(
            f'<section class="mode-card">'
            f'<h2>{html.escape(fmid)} '
            f'<span class="pill pill-{method}" title="{html.escape(method_note)}">{method}</span></h2>'
            f'<p class="muted">{len(rows)} run(s) recorded — latest: {html.escape(latest_summary)}</p>'
            f"{charts}"
            f"<h4>All runs — full detail</h4>"
            f'<p class="chart-note">Every field recorded for every run of this failure mode, newest first. '
            f'Hover a column header for what it means, or see the glossary above.</p>'
            f"{_table(rows)}"
            f"</section>"
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    body = "".join(sections) if sections else '<p class="muted">No metrics history recorded yet.</p>'
    glossary = _glossary_html()

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Eval Metrics Dashboard</title>
<style>
  :root {{
    color-scheme: light;
    --surface-1: #fcfcfb; --page: #f9f9f7;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --muted: #898781;
    --gridline: #e1e0d9; --baseline: #c3c2b7; --border: rgba(11,11,11,0.10);
    --series-1: {SERIES_1_LIGHT}; --series-2: {SERIES_2_LIGHT}; --band: {BAND_LIGHT};
    --row-ok: #eafaea; --row-regressed: #fceaea;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface-1: #1a1a19; --page: #0d0d0d;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --muted: #898781;
      --gridline: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,0.10);
      --series-1: {SERIES_1_DARK}; --series-2: {SERIES_2_DARK}; --band: {BAND_DARK};
      --row-ok: #12271a; --row-regressed: #2a1414;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--page); color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  header {{ padding: 24px 32px; border-bottom: 1px solid var(--border); }}
  header h1 {{ margin: 0 0 4px; font-size: 20px; }}
  header p {{ margin: 0; color: var(--text-secondary); font-size: 13px; }}
  main {{ padding: 24px 32px; display: flex; flex-direction: column; gap: 20px; max-width: 960px; margin: 0 auto; }}
  .mode-card {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px 24px;
  }}
  .mode-card h2 {{ margin: 0 0 4px; font-size: 16px; display: flex; align-items: center; gap: 8px; }}
  .mode-card h4 {{ margin: 16px 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-secondary); }}
  .pill {{ font-size: 10px; padding: 2px 8px; border-radius: 999px; font-weight: 600; text-transform: uppercase; }}
  .pill-code {{ background: var(--band); color: var(--text-primary); }}
  .pill-judge {{ background: var(--series-2); color: #fff; }}
  .muted {{ color: var(--text-secondary); font-size: 13px; }}
  .chart-svg {{ display: block; }}
  .gridline {{ stroke: var(--gridline); stroke-width: 1; }}
  .tick {{ fill: var(--muted); font-size: 9px; }}
  .series-line {{ stroke-width: 2; }}
  .ci-band {{ fill: var(--band); opacity: .5; }}
  .legend {{ display: flex; gap: 14px; align-items: center; font-size: 11px; color: var(--text-secondary); margin: 4px 0 8px; flex-wrap: wrap; }}
  .legend .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }}
  .band-dot {{ background: var(--band); opacity: .7; border-radius: 2px !important; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 11px; }}
  th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--gridline); text-align: left; white-space: nowrap; }}
  th {{ color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 9px; letter-spacing: .03em; cursor: help; }}
  tr.row-ok {{ background: var(--row-ok); }}
  tr.row-regressed {{ background: var(--row-regressed); }}
  .chart-note {{ font-size: 12px; color: var(--text-secondary); margin: 0 0 10px; max-width: 640px; line-height: 1.5; }}
  .glossary {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
    padding: 14px 20px;
  }}
  .glossary summary {{ cursor: pointer; font-weight: 600; font-size: 13px; }}
  .glossary-table {{ margin-top: 10px; }}
  .glossary-table th {{ cursor: default; }}
  .glossary-table td:first-child {{ white-space: nowrap; font-weight: 600; color: var(--text-primary); }}
  .glossary-table td:last-child {{ color: var(--text-secondary); font-size: 12px; line-height: 1.5; }}
  code {{ background: var(--gridline); padding: 1px 5px; border-radius: 4px; font-size: 11px; }}
</style>
</head>
<body>
<header>
  <h1>Eval Metrics Dashboard</h1>
  <p>Generated {html.escape(generated_at)} · {len(history)} run(s) across {len(by_mode)} failure mode(s) · source: evals/results/metrics_history.jsonl</p>
</header>
<main>
{glossary}
{body}
</main>
</body>
</html>
"""


def main() -> None:
    history = read_jsonl(MetricsHistoryRecord, HISTORY_PATH) if HISTORY_PATH.exists() else []
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render(history))
    print(f"wrote {OUT_PATH} ({len(history)} history row(s))")


if __name__ == "__main__":
    main()
