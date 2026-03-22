#!/usr/bin/env python3
"""Compare JOB full Q-error curves: 20260218 baseline vs cost/numworkers run.

Same visual style as `job_zero_t3_results_20260218_qerror_line.png` (sorted
Q-error lines + dashed verticals at avg, p50, p75, p90). Vertical reference
lines are computed from the 20260218 file so they match the standalone plot.
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

JOB_20260218 = ROOT / "job_zero_t3_results_20260218.txt"
JOB_COST_NUMWORKERS = ROOT / "job_zero_t3_results_cost_numworkers.txt"

OUT_PNG = ROOT / "job_20260218_vs_cost_numworkers_qerror_line.png"

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

    q_20260218 = parse_job_qerrors(JOB_20260218)
    q_cost = parse_job_qerrors(JOB_COST_NUMWORKERS)

    if not q_20260218 or not q_cost:
        raise SystemExit("Failed to parse q-errors from one or both JOB result files.")
    if len(q_20260218) != len(q_cost):
        raise SystemExit(
            f"Query count mismatch: {len(q_20260218)} vs {len(q_cost)} — both files must align."
        )

    if _HAS_NUMPY:
        sorted_20260218 = np.sort(np.array(q_20260218, dtype=float))
        sorted_cost = np.sort(np.array(q_cost, dtype=float))
        x_axis = np.arange(1, len(sorted_20260218) + 1)
    else:
        sorted_20260218 = sorted(q_20260218)
        sorted_cost = sorted(q_cost)
        x_axis = list(range(1, len(sorted_20260218) + 1))

    # Reference lines from 20260218 (same as standalone job_zero_t3_results_20260218_qerror_line.png)
    ref_stats = compute_stats(q_20260218)
    idx = _rank_indices(sorted_20260218, ref_stats)

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(x_axis, sorted_20260218, color="#2980b9", linewidth=1.2, label="20260218")
    ax.plot(x_axis, sorted_cost, color="#e67e22", linewidth=1.2, label="cost / numworkers")

    ax.axvline(x=idx["avg"], color="#e74c3c", linestyle="--", linewidth=1.5, label=f"avg={ref_stats['avg']:.4f}")
    ax.axvline(x=idx["p50"], color="#27ae60", linestyle="--", linewidth=1.5, label=f"p50={ref_stats['p50']:.4f}")
    ax.axvline(x=idx["p75"], color="#f39c12", linestyle="--", linewidth=1.5, label=f"p75={ref_stats['p75']:.4f}")
    ax.axvline(x=idx["p90"], color="#8e44ad", linestyle="--", linewidth=1.5, label=f"p90={ref_stats['p90']:.4f}")

    ax.set_xlabel("Number of queries")
    ax.set_ylabel("Q-error")
    ax.set_title(
        "Q-error per query (JOB full) — 20260218 vs cost/numworkers; vertical lines at avg, p50, p75, p90 (20260218)"
    )
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylim(1, None)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("Saved", OUT_PNG)


if __name__ == "__main__":
    main()
