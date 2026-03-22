#!/usr/bin/env python3
"""Generate JOB full Q-error comparison plot.

This reproduces and extends the existing `job_comparison.png` figure by
plotting three JOB result files:

- 20260218 baseline
- 20260309 full features (reference run)
- estimates-only run

All three lines show the sorted per-query Q-error. The vertical reference
lines (avg, p50, p75, p90) are computed from the full-features run.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_NUMPY = False

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _HAS_MATPLOTLIB = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_MATPLOTLIB = False


ROOT = Path(__file__).resolve().parent

JOB_BASELINE = ROOT / "job_zero_t3_results_20260218.txt"
JOB_FULL_FEATURES = ROOT / "job_zero_t3_results_20260309_full_features.txt"
JOB_ESTIMATES = ROOT / "job_zero_t3_results_estimates.txt"

OUT_PNG = ROOT / "job_comparison.png"

JOB_QERROR = re.compile(r"q_error=([\d.]+)")


def parse_job_qerrors(path: Path) -> list[float]:
    qerrors: list[float] = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if line.startswith("Test set ("):
            continue
        m = JOB_QERROR.search(line)
        if m:
            qerrors.append(float(m.group(1)))
    return qerrors


def compute_stats(qerrors: list[float]) -> dict[str, float]:
    if not qerrors:
        return {"avg": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0}

    if _HAS_NUMPY:
        arr = np.array(qerrors, dtype=float)
        return {
            "avg": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p75": float(np.percentile(arr, 75)),
            "p90": float(np.percentile(arr, 90)),
        }

    s = sorted(qerrors)
    n = len(s)
    avg = sum(s) / n

    def percentile(p: float) -> float:
        if n == 1:
            return s[0]
        idx = int(p * (n - 1))
        return s[idx]

    return {
        "avg": avg,
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
    }


def _rank_indices(sorted_q: list[float] | "np.ndarray", stats: dict[str, float]) -> dict[str, int]:
    if _HAS_NUMPY and isinstance(sorted_q, np.ndarray):
        idx_avg = int(np.searchsorted(sorted_q, stats["avg"], side="left")) + 1
        idx_p50 = int(np.searchsorted(sorted_q, stats["p50"], side="left")) + 1
        idx_p75 = int(np.searchsorted(sorted_q, stats["p75"], side="left")) + 1
        idx_p90 = int(np.searchsorted(sorted_q, stats["p90"], side="left")) + 1
        return {
            "avg": idx_avg,
            "p50": idx_p50,
            "p75": idx_p75,
            "p90": idx_p90,
        }

    # Fallback without numpy
    def rank(v: float) -> int:
        for i, q in enumerate(sorted_q):
            if q >= v:
                return i + 1
        return len(sorted_q)

    return {
        "avg": rank(stats["avg"]),
        "p50": rank(stats["p50"]),
        "p75": rank(stats["p75"]),
        "p90": rank(stats["p90"]),
    }


def main() -> None:
    if not _HAS_MATPLOTLIB:
        raise SystemExit("matplotlib is required to generate the comparison plot.")

    baseline_q = parse_job_qerrors(JOB_BASELINE)
    full_q = parse_job_qerrors(JOB_FULL_FEATURES)
    est_q = parse_job_qerrors(JOB_ESTIMATES)

    if not baseline_q or not full_q or not est_q:
        raise SystemExit("Failed to parse q-errors from one or more JOB result files.")

    # Sort q-errors independently for visual comparison
    if _HAS_NUMPY:
        baseline_sorted = np.sort(np.array(baseline_q, dtype=float))
        full_sorted = np.sort(np.array(full_q, dtype=float))
        est_sorted = np.sort(np.array(est_q, dtype=float))
        x_axis = np.arange(1, len(full_sorted) + 1)
    else:
        baseline_sorted = sorted(baseline_q)
        full_sorted = sorted(full_q)
        est_sorted = sorted(est_q)
        x_axis = list(range(1, len(full_sorted) + 1))

    # Reference statistics and vertical lines from the full-features run
    full_stats = compute_stats(full_q)
    idx = _rank_indices(full_sorted, full_stats)

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(x_axis, baseline_sorted, color="#2980b9", linewidth=1.2, label="20260218")
    ax.plot(x_axis, full_sorted, color="#e67e22", linewidth=1.5, label="20260309 full features")
    ax.plot(x_axis, est_sorted, color="#16a085", linewidth=1.5, label="estimates")

    ax.axvline(x=idx["avg"], color="#e74c3c", linestyle="--", linewidth=1.5, label=f"avg={full_stats['avg']:.4f}")
    ax.axvline(x=idx["p50"], color="#27ae60", linestyle="--", linewidth=1.5, label=f"p50={full_stats['p50']:.4f}")
    ax.axvline(x=idx["p75"], color="#f39c12", linestyle="--", linewidth=1.5, label=f"p75={full_stats['p75']:.4f}")
    ax.axvline(x=idx["p90"], color="#8e44ad", linestyle="--", linewidth=1.5, label=f"p90={full_stats['p90']:.4f}")

    ax.set_xlabel("Number of queries")
    ax.set_ylabel("Q-error")
    ax.set_title("Q-error per query (JOB full) — both versions + estimates, ref lines from full features")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylim(1, None)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

