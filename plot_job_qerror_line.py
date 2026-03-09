#!/usr/bin/env python3
"""Plot Q-error per query (sorted) with vertical lines at avg, p50, p75, p90.
Same style as holdout_job_qerror_line.png.

Usage:
  python -m plot_job_qerror_line job_zero_t3_results_20260309_full_features.txt
  python -m plot_job_qerror_line job_zero_t3_results.txt -o my_plot.png
  python -m plot_job_qerror_line job_zero_t3_results_20260218.txt --compare job_zero_t3_results_20260309_full_features.txt
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
JOB_QERROR = re.compile(r"q_error=([\d.]+)")


def _compute_stats(qerrors: list[float]) -> tuple[float, float, float, float]:
    """Return (avg, p50, p75, p90)."""
    if _HAS_NUMPY:
        arr = np.array(qerrors)
        return (
            float(np.mean(arr)),
            float(np.percentile(arr, 50)),
            float(np.percentile(arr, 75)),
            float(np.percentile(arr, 90)),
        )
    s = sorted(qerrors)
    nq = len(s)
    avg = sum(qerrors) / nq
    p50 = s[int(0.50 * (nq - 1))] if nq else 0
    p75 = s[int(0.75 * (nq - 1))] if nq else 0
    p90 = s[int(0.90 * (nq - 1))] if nq else 0
    return avg, p50, p75, p90


def _rank_indices(sorted_q: list[float], avg: float, p50: float, p75: float, p90: float) -> tuple[int, int, int, int]:
    """Return (idx_avg, idx_p50, idx_p75, idx_p90) for vertical lines."""
    if _HAS_NUMPY:
        arr = np.array(sorted_q)
        return (
            int(np.searchsorted(arr, avg, side="left")) + 1,
            int(np.searchsorted(arr, p50, side="left")) + 1,
            int(np.searchsorted(arr, p75, side="left")) + 1,
            int(np.searchsorted(arr, p90, side="left")) + 1,
        )
    def rank(v):
        for i, q in enumerate(sorted_q):
            if q >= v:
                return i + 1
        return len(sorted_q)
    return rank(avg), rank(p50), rank(p75), rank(p90)


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


def _resolve_path(p: Path) -> Path:
    return p if p.is_absolute() else ROOT / p


def _plot_single(
    qerrors: list[float],
    out_path: Path,
    title: str = "Q-error per query (JOB full) — vertical lines at avg, p50, p75, p90",
) -> None:
    """Create single-curve plot with vertical lines from this data."""
    avg, p50, p75, p90 = _compute_stats(qerrors)
    sorted_q = sorted(qerrors)
    if _HAS_NUMPY:
        sorted_q = np.array(sorted_q)
    x_axis = np.arange(1, len(sorted_q) + 1) if _HAS_NUMPY else list(range(1, len(sorted_q) + 1))
    idx_avg, idx_p50, idx_p75, idx_p90 = _rank_indices(list(sorted_q), avg, p50, p75, p90)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_axis, sorted_q, color="#2980b9", linewidth=1.2, label="q-error (sorted)")
    ax.axvline(x=idx_avg, color="#e74c3c", linestyle="--", linewidth=1.5, label=f"avg={avg:.4f}")
    ax.axvline(x=idx_p50, color="#27ae60", linestyle="--", linewidth=1.5, label=f"p50={p50:.4f}")
    ax.axvline(x=idx_p75, color="#f39c12", linestyle="--", linewidth=1.5, label=f"p75={p75:.4f}")
    ax.axvline(x=idx_p90, color="#8e44ad", linestyle="--", linewidth=1.5, label=f"p90={p90:.4f}")
    ax.set_xlabel("Number of queries")
    ax.set_ylabel("Q-error")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylim(1, None)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("Saved", out_path)


def _plot_compare(
    qerrors_a: list[float],
    qerrors_b: list[float],
    label_a: str,
    label_b: str,
    out_path: Path,
    stats_from: str,
) -> None:
    """Create comparison plot: both curves, vertical lines from full features (stats_from='b')."""
    # Use stats and vertical line positions from the "full features" curve (b)
    avg, p50, p75, p90 = _compute_stats(qerrors_b)
    sorted_b = sorted(qerrors_b)
    idx_avg, idx_p50, idx_p75, idx_p90 = _rank_indices(sorted_b, avg, p50, p75, p90)

    sorted_a = sorted(qerrors_a)
    n = max(len(sorted_a), len(sorted_b))
    x_axis = np.arange(1, n + 1) if _HAS_NUMPY else list(range(1, n + 1))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_axis[: len(sorted_a)], sorted_a, color="#2980b9", linewidth=1.2, label=label_a)
    ax.plot(x_axis[: len(sorted_b)], sorted_b, color="#e67e22", linewidth=1.2, label=label_b)
    ax.axvline(x=idx_avg, color="#e74c3c", linestyle="--", linewidth=1.5, label=f"avg={avg:.4f}")
    ax.axvline(x=idx_p50, color="#27ae60", linestyle="--", linewidth=1.5, label=f"p50={p50:.4f}")
    ax.axvline(x=idx_p75, color="#f39c12", linestyle="--", linewidth=1.5, label=f"p75={p75:.4f}")
    ax.axvline(x=idx_p90, color="#8e44ad", linestyle="--", linewidth=1.5, label=f"p90={p90:.4f}")
    ax.set_xlabel("Number of queries")
    ax.set_ylabel("Q-error")
    ax.set_title("Q-error per query (JOB full) — both versions, ref lines from full features")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylim(1, None)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("Saved", out_path)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Plot Q-error line (sorted) with avg, p50, p75, p90.")
    ap.add_argument("job_file", type=Path, help="job_zero_t3_results file")
    ap.add_argument("--compare", type=Path, default=None,
                    help="Second file for comparison; both curves in one plot, ref lines from this (full features)")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="Output PNG path (default: <job_file_stem>_qerror_line.png)")
    ap.add_argument("--compare-out", type=Path, default=None,
                    help="Output PNG for comparison plot (default: <job_file_stem>_vs_full_features_qerror_line.png)")
    args = ap.parse_args()

    job_path = _resolve_path(args.job_file)
    if not job_path.exists():
        print("File not found:", job_path)
        return

    if not _HAS_MATPLOTLIB:
        print("matplotlib is required")
        return

    qerrors = parse_job_qerrors(job_path)
    if not qerrors:
        print("No q-errors parsed from", job_path)
        return

    # Single plot
    out_path = args.out
    if out_path is None:
        out_path = ROOT / f"{job_path.stem}_qerror_line.png"
    else:
        out_path = _resolve_path(out_path)
    _plot_single(qerrors, out_path)

    # Comparison plot (if --compare given)
    if args.compare is not None:
        compare_path = _resolve_path(args.compare)
        if not compare_path.exists():
            print("Compare file not found:", compare_path)
            return
        qerrors_b = parse_job_qerrors(compare_path)
        if not qerrors_b:
            print("No q-errors parsed from", compare_path)
            return
        compare_out = args.compare_out
        if compare_out is None:
            compare_out = ROOT / f"{job_path.stem}_vs_{compare_path.stem}_qerror_line.png"
        else:
            compare_out = _resolve_path(compare_out)
        label_a = job_path.stem.replace("job_zero_t3_results_", "").replace("_", " ")
        label_b = compare_path.stem.replace("job_zero_t3_results_", "").replace("_", " ")
        _plot_compare(qerrors, qerrors_b, label_a, label_b, compare_out, stats_from="b")


if __name__ == "__main__":
    main()
