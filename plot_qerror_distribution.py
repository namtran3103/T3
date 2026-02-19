"""
Produce a frequency distribution plot of q-errors for T3 predictions on a test set.

Uses a specified model path and data root (parsed_plans). Infers the test set from the
model name (e.g. model_zero_holdout_tpcds.txt -> tpcds). Loads test JSONs from
data_root/<test_set>, runs the model, computes per-query q-errors, and plots a dual
histogram: left subplot Q-Error 1–10 (narrow bins), right subplot 10–30 (wider bins),
with annotations on low-frequency bars. Saves the figure in the project root.

Usage (from T3 project root):
  python plot_qerror_distribution.py --model model_zero_holdout_tpcds.txt
  python plot_qerror_distribution.py --model /path/to/model.txt --data /path/to/parsed_plans --out qerror_dist.png
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb

from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.zeroshot.training_zeroshot_tpch_holdout import (
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons

DEFAULT_DATA_DIR = Path("/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans")


def infer_test_set_from_model_path(model_path: Path) -> str | None:
    """
    Infer holdout/test set name from model file stem.
    E.g. model_zero_holdout_tpcds.txt -> tpcds, model_zero_holdout_imdb_full_v2.txt -> imdb_full.
    """
    stem = model_path.stem
    prefix = "model_zero_holdout_"
    if not stem.startswith(prefix):
        return None
    name = stem[len(prefix) :]
    name = re.sub(r"_v\d+$", "", name)
    return name or None


def compute_qerrors(model_path: Path, data_dir: Path, test_set: str) -> list[float]:
    """Load model and test queries, return list of per-query q-errors."""
    all_paths = collect_all_zeroshot_jsons(data_dir)
    _, test_paths = split_train_test_by_holdout(all_paths, holdout_name=test_set)
    if not test_paths:
        return []

    queries = load_benchmarked_queries_from_zeroshot(test_paths)
    if not queries:
        return []

    booster = lgb.Booster(model_file=str(model_path))
    model = PerTupleTreeModel(booster)
    errors = []
    for b in queries:
        pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        errors.append(q_error(actual, pred))
    return errors


def plot_qerror_distribution(
    qerrors: list[float],
    test_set_name: str,
    out_path: Path,
    title: str | None = None,
) -> None:
    """
    Plot dual histogram: left 1–10 (bin width 0.5), right 10–30 (bin width 2).
    Shared y-axis (scale up to 3000), blue bars with black edges, annotate low-frequency bars.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise RuntimeError("matplotlib is required to generate the plot") from e

    arr = np.array(qerrors)
    # Left: 1 to 10, bins of 0.5 -> 18 bins
    left_edges = np.arange(1.0, 10.0 + 0.5, 0.5)
    # Right: 10 to 30, bins of 2 -> 10, 12, ..., 30
    right_edges = np.arange(10.0, 30.0 + 2.0, 2.0)

    left_counts, _ = np.histogram(arr, bins=left_edges)
    right_counts, _ = np.histogram(arr, bins=right_edges)

    left_centers = (left_edges[:-1] + left_edges[1:]) / 2
    right_centers = (right_edges[:-1] + right_edges[1:]) / 2

    fig, (ax_left, ax_right) = plt.subplots(1, 2, sharey=True, figsize=(10, 5))
    y_max = max(left_counts.max() if len(left_counts) else 0, right_counts.max() if len(right_counts) else 0)
    y_max = max(y_max, 1)
    y_axis_max = max(3000, int(np.ceil(y_max / 500) * 500))
    y_ticks = list(range(0, y_axis_max + 1, 500))

    # Left subplot
    width_left = 0.5 * 0.9
    bars_left = ax_left.bar(
        left_centers,
        left_counts,
        width=width_left,
        color="blue",
        edgecolor="black",
        linewidth=0.8,
    )
    ax_left.set_xlim(1, 10)
    ax_left.set_ylim(0, y_axis_max * 1.02)
    ax_left.set_xticks([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    ax_left.set_yticks(y_ticks)
    ax_left.grid(True, color="gray", linestyle="-", linewidth=0.5, alpha=0.7)
    ax_left.set_ylabel("Frequency")
    for bar, count in zip(bars_left, left_counts):
        if 0 < count <= 15:
            ax_left.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (y_axis_max * 0.005),
                str(int(count)),
                ha="center",
                va="bottom",
                fontsize=9,
            )

    # Right subplot
    width_right = 2.0 * 0.9
    bars_right = ax_right.bar(
        right_centers,
        right_counts,
        width=width_right,
        color="blue",
        edgecolor="black",
        linewidth=0.8,
    )
    ax_right.set_xlim(10, 30)
    ax_right.set_ylim(0, y_axis_max * 1.02)
    ax_right.set_xticks([10, 15, 20, 25, 30])
    ax_right.set_yticks(y_ticks)
    ax_right.grid(True, color="gray", linestyle="-", linewidth=0.5, alpha=0.7)
    for bar, count in zip(bars_right, right_counts):
        if 0 < count <= 15:
            ax_right.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (y_axis_max * 0.005),
                str(int(count)),
                ha="center",
                va="bottom",
                fontsize=9,
            )

    fig.text(0.5, -0.02, "Q-Error of Test Queries", ha="center", fontsize=11)
    if title is None:
        title = f"Frequency distribution of different q-errors for T3 predictions on all {test_set_name} test queries."
    fig.suptitle(title, fontsize=11, y=1.02)
    plt.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot q-error frequency distribution for a zero-shot holdout model."
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Path to model file (e.g. model_zero_holdout_tpcds.txt)",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Root directory containing parsed_plans (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output image path (default: qerror_distribution_<test_set>.png in project root)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional figure title (default: includes test set name)",
    )
    args = parser.parse_args()

    model_path = args.model if args.model.is_absolute() else _repo / args.model
    if not model_path.is_file():
        print(f"Error: model file not found: {model_path}")
        sys.exit(1)

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    test_set = infer_test_set_from_model_path(model_path)
    if not test_set:
        print("Error: could not infer test set from model name. Expected stem like model_zero_holdout_<name>.txt")
        sys.exit(1)

    print(f"Model: {model_path}")
    print(f"Data: {data_dir}")
    print(f"Inferred test set: {test_set}")

    qerrors = compute_qerrors(model_path, data_dir, test_set)
    if not qerrors:
        print("Error: no q-errors computed (no test queries loaded).")
        sys.exit(1)

    print(f"Computed {len(qerrors)} q-errors (min={min(qerrors):.4f}, max={max(qerrors):.4f}, p50={np.median(qerrors):.4f})")

    out_path = args.out
    if out_path is None:
        out_path = _repo / f"qerror_distribution_{test_set}.png"
    else:
        out_path = out_path if out_path.is_absolute() else _repo / out_path

    plot_qerror_distribution(
        qerrors,
        test_set_name=test_set,
        out_path=out_path,
        title=args.title,
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
