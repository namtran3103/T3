#!/usr/bin/env python3
"""Build a markdown report from:
1) holdout.txt sections: median over datasets (avg, p50, p90, min, max), p50 bar chart.
   - lines 79-99: Holdout summary
   - lines 182-202: Full run new features implementation
   - lines 271-291: Full run with act cards, rm startswith and between, large vector
2) job_zero_t3_results file: line plot of q-error for all queries, with vertical lines at avg, p50, p75, p90.

Usage:
  python -m holdout_job_to_md
  python -m holdout_job_to_md --holdout holdout.txt --job job_zero_t3_results_20260218.txt --out report.md
  python -m holdout_job_to_md --holdout-start 79 --holdout-end 99   # single section only
"""

import re
from pathlib import Path

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False

ROOT = Path(__file__).resolve().parent
HOLDOUT_FILE = ROOT / "holdout.txt"
JOB_RESULTS_FILE = ROOT / "job_zero_t3_results_20260218.txt"
OUTPUT_MD = ROOT / "holdout_job_report.md"

# Multiple holdout sections: (start_line, end_line, title, bar_filename)
HOLDOUT_SECTIONS = [
    (79, 99, "Holdout summary (lines 79–99)", "holdout_job_p50_bars.png"),
    (182, 202, "Full run new features implementation", "holdout_new_features_p50_bars.png"),
    (271, 291, "Full run with act cards, rm startswith and between, large vector", "holdout_act_cards_p50_bars.png"),
]

# holdout: Test set (name, N queries): q-error avg=X p50=Y p90=Z min=M max=Max
HOLDOUT_LINE = re.compile(
    r"Test set \((\w+),\s*(\d+)\s*queries\):\s*q-error\s+"
    r"avg=([\d.]+)\s+p50=([\d.]+)\s+p90=([\d.]+)\s+"
    r"min=([\d.]+)\s+max=([\d.]+)"
)
# job: job_full_c8220_0: pred=... actual=... q_error=1.7443
JOB_QERROR = re.compile(r"q_error=([\d.]+)")


def parse_holdout_slice(path: Path, start: int, end: int) -> list[dict]:
    """Parse holdout file lines [start, end] (1-based) into list of row dicts."""
    lines = path.read_text().strip().splitlines()
    rows = []
    for i in range(start - 1, min(end, len(lines))):
        line = lines[i].strip()
        m = HOLDOUT_LINE.match(line)
        if m:
            rows.append({
                "dataset": m.group(1),
                "queries": int(m.group(2)),
                "avg": float(m.group(3)),
                "p50": float(m.group(4)),
                "p90": float(m.group(5)),
                "min": float(m.group(6)),
                "max": float(m.group(7)),
            })
    return rows


def parse_job_qerrors(path: Path) -> list[float]:
    """Extract q_error value from each per-query line (skip summary line)."""
    qerrors = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if line.startswith("Test set ("):
            continue
        m = JOB_QERROR.search(line)
        if m:
            qerrors.append(float(m.group(1)))
    return qerrors


def format_num(x: float) -> str:
    return f"{x:.4f}"


def _median(vals: list[float]) -> float:
    """Median of a list (works without numpy)."""
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Holdout (79-99) + JOB results → markdown and charts.")
    ap.add_argument("--holdout", type=Path, default=HOLDOUT_FILE, help="holdout.txt")
    ap.add_argument("--job", type=Path, default=JOB_RESULTS_FILE, help="job_zero_t3_results file")
    ap.add_argument("--out", type=Path, default=OUTPUT_MD, help="Output markdown path")
    ap.add_argument("--plot-out", type=Path, default=None, help="Output path for q-error line plot (default: same dir as --out)")
    ap.add_argument("--holdout-start", type=int, default=None, help="First holdout line (1-based); if set, only this single section is used")
    ap.add_argument("--holdout-end", type=int, default=None, help="Last holdout line (1-based); used with --holdout-start")
    args = ap.parse_args()

    holdout_path = args.holdout if args.holdout.is_absolute() else ROOT / args.holdout
    job_path = args.job if args.job.is_absolute() else ROOT / args.job
    out_path = args.out if args.out.is_absolute() else ROOT / args.out

    # Determine which sections to process
    if args.holdout_start is not None and args.holdout_end is not None:
        sections = [(args.holdout_start, args.holdout_end, "Holdout", "holdout_job_p50_bars.png")]
    else:
        sections = HOLDOUT_SECTIONS

    md_lines = [
        "# Holdout (non-enriched) + JOB Q-Error Report",
        "",
    ]

    for sec_idx, (start, end, title, bar_name) in enumerate(sections, start=1):
        rows = parse_holdout_slice(holdout_path, start, end)
        if not rows:
            print("No holdout rows parsed from", holdout_path, "lines", start, "-", end)
            continue

        n = len(rows)
        med_avg = _median([r["avg"] for r in rows])
        med_p50 = _median([r["p50"] for r in rows])
        med_p90 = _median([r["p90"] for r in rows])
        med_min = _median([r["min"] for r in rows])
        med_max = _median([r["max"] for r in rows])

        md_lines.extend([
            f"## {sec_idx}. {title}",
            "",
            f"**Datasets:** {n}",
            "",
            "### Median over datasets",
            "",
            "| Metric | Value |",
            "|--------|------:|",
            f"| **avg** | {format_num(med_avg)} |",
            f"| **p50** | {format_num(med_p50)} |",
            f"| **p90** | {format_num(med_p90)} |",
            f"| **min** | {format_num(med_min)} |",
            f"| **max** | {format_num(med_max)} |",
            "",
        ])

        # p50 bar chart
        bar_path = out_path.parent / bar_name
        if _HAS_MATPLOTLIB:
            p50_vals = [r["p50"] for r in rows]
            names = [r["dataset"] for r in rows]
            fig, ax = plt.subplots(figsize=(14, 5))
            x = range(len(names))
            ax.bar(x, p50_vals, color="#c0392b", width=0.5, edgecolor="none")
            ax.set_xticks(x)
            ax.set_xticklabels(names, rotation=45, ha="right")
            ax.set_ylabel("p50")
            ax.set_title(f"Q-error p50 by dataset ({title})")
            ax.set_ylim(1, None)
            fig.tight_layout()
            fig.savefig(bar_path, dpi=120, bbox_inches="tight")
            plt.close(fig)
            md_lines.extend([
                "### p50 by dataset",
                "",
                f"![p50 bars]({bar_path.name})",
                "",
            ])
        else:
            md_lines.append("*(Install matplotlib to generate p50 bar chart.)*")
            md_lines.append("")

    # ----- JOB results: q-error line + vertical lines at avg, p50, p75, p90 -----
    job_section_num = len(sections) + 1
    qerrors = parse_job_qerrors(job_path)
    if not qerrors:
        print("No q-errors parsed from", job_path)
    else:
        md_lines.extend([
            f"## {job_section_num}. JOB full q-error (all queries)",
            "",
            f"**Queries:** {len(qerrors)}",
            "",
        ])
        if _HAS_NUMPY:
            arr = np.array(qerrors)
            avg = float(np.mean(arr))
            p50 = float(np.percentile(arr, 50))
            p75 = float(np.percentile(arr, 75))
            p90 = float(np.percentile(arr, 90))
            qmin = float(np.min(arr))
            qmax = float(np.max(arr))
        else:
            s = sorted(qerrors)
            nq = len(s)
            avg = sum(qerrors) / nq
            p50 = s[int(0.50 * (nq - 1))] if nq else 0
            p75 = s[int(0.75 * (nq - 1))] if nq else 0
            p90 = s[int(0.90 * (nq - 1))] if nq else 0
            qmin = min(qerrors)
            qmax = max(qerrors)
        md_lines.extend([
            "| Metric | Value |",
            "|--------|------:|",
            f"| **avg** | {format_num(avg)} |",
            f"| **p50** | {format_num(p50)} |",
            f"| **p75** | {format_num(p75)} |",
            f"| **p90** | {format_num(p90)} |",
            f"| **min** | {format_num(qmin)} |",
            f"| **max** | {format_num(qmax)} |",
            "",
        ])

        line_path = args.plot_out if args.plot_out is not None else out_path.parent / "holdout_job_qerror_line.png"
        if not line_path.is_absolute():
            line_path = ROOT / line_path
        if _HAS_MATPLOTLIB:
            sorted_q = sorted(qerrors)
            if _HAS_NUMPY:
                sorted_q = np.array(sorted_q)
                x_axis = np.arange(1, len(sorted_q) + 1)
                idx_avg = int(np.searchsorted(sorted_q, avg, side="left")) + 1
                idx_p50 = int(np.searchsorted(sorted_q, p50, side="left")) + 1
                idx_p75 = int(np.searchsorted(sorted_q, p75, side="left")) + 1
                idx_p90 = int(np.searchsorted(sorted_q, p90, side="left")) + 1
            else:
                x_axis = list(range(1, len(sorted_q) + 1))
                def rank(v):
                    for i, q in enumerate(sorted_q):
                        if q >= v:
                            return i + 1
                    return len(sorted_q)
                idx_avg = rank(avg)
                idx_p50 = rank(p50)
                idx_p75 = rank(p75)
                idx_p90 = rank(p90)
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(x_axis, sorted_q, color="#2980b9", linewidth=1.2, label="q-error (sorted)")
            ax.axvline(x=idx_avg, color="#e74c3c", linestyle="--", linewidth=1.5, label=f"avg={avg:.4f}")
            ax.axvline(x=idx_p50, color="#27ae60", linestyle="--", linewidth=1.5, label=f"p50={p50:.4f}")
            ax.axvline(x=idx_p75, color="#f39c12", linestyle="--", linewidth=1.5, label=f"p75={p75:.4f}")
            ax.axvline(x=idx_p90, color="#8e44ad", linestyle="--", linewidth=1.5, label=f"p90={p90:.4f}")
            ax.set_xlabel("Number of queries")
            ax.set_ylabel("Q-error")
            ax.set_title("Q-error per query (JOB full) — vertical lines at avg, p50, p75, p90")
            ax.legend(loc="upper left", fontsize=8)
            ax.set_ylim(1, None)
            fig.tight_layout()
            fig.savefig(line_path, dpi=120, bbox_inches="tight")
            plt.close(fig)
            md_lines.extend([
                "### Q-error line (sorted) with avg, p50, p75, p90",
                "",
                f"![q-error line]({line_path.name})",
                "",
            ])
        else:
            md_lines.append("*(Install matplotlib to generate q-error line chart.)*")
            md_lines.append("")

    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    print("Wrote", out_path)


if __name__ == "__main__":
    main()
