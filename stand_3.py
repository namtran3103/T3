#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


LINE_RE = re.compile(
    r"^Test set \((?P<dataset>[^,]+),\s+\d+\s+queries\):\s+"
    r"q-error avg=(?P<avg>\d+\.\d+)\s+"
    r"p50=(?P<p50>\d+\.\d+)\s+"
    r"p90=(?P<p90>\d+\.\d+)\s+"
    r"min=(?P<min>\d+\.\d+)\s+"
    r"max=(?P<max>\d+\.\d+)\s*$"
)
METRICS = ["p50", "p90"]


def parse_block(lines, start_line, end_line):
    block = {}
    for idx in range(start_line - 1, end_line):
        line = lines[idx].strip()
        m = LINE_RE.match(line)
        if not m:
            continue
        dataset = m.group("dataset")
        block[dataset] = {
            "avg": float(m.group("avg")),
            "p50": float(m.group("p50")),
            "p90": float(m.group("p90")),
            "min": float(m.group("min")),
            "max": float(m.group("max")),
        }
    return block


def median_metrics(block, datasets):
    medians = {}
    for metric in METRICS:
        medians[metric] = float(np.median([block[d][metric] for d in datasets]))
    return medians


def mean_metrics(block, datasets):
    means = {}
    for metric in METRICS:
        means[metric] = float(np.mean([block[d][metric] for d in datasets]))
    return means


def main():
    parser = argparse.ArgumentParser(
        description="Plot grouped p50 bars for three holdout configurations."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="holdout.txt",
        help="Path to holdout.txt (default: holdout.txt)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="stand_3_p50_comparison.png",
        help="Output image path (default: stand_3_p50_comparison.png)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    lines = input_path.read_text(encoding="utf-8").splitlines()

    t3 = parse_block(lines, 143, 163)
    updated_actual_cards = parse_block(lines, 361, 381)
    updated_est_cards = parse_block(lines, 385, 405)

    datasets = [d for d in t3 if d in updated_actual_cards and d in updated_est_cards]
    if not datasets:
        raise ValueError("No overlapping datasets found across all three sections.")

    x = np.arange(len(datasets))
    width = 0.26

    vals_t3 = [t3[d]["p50"] for d in datasets]
    vals_actual = [updated_actual_cards[d]["p50"] for d in datasets]
    vals_est = [updated_est_cards[d]["p50"] for d in datasets]

    fig, ax = plt.subplots(figsize=(18, 11))
    ax.bar(x - width, vals_t3, width=width, label="force umbra mapping", color="#4C78A8")
    ax.bar(
        x,
        vals_actual,
        width=width,
        label="postgres feature vector (act cards)",
        color="#59A14F",
    )
    ax.bar(
        x + width,
        vals_est,
        width=width,
        label="postgres feature vector (est cards)",
        color="#F28E2B",
    )

    ax.set_title("p50 q-error per dataset (three setups)")
    ax.set_ylabel("p50 q-error")
    ax.set_xlabel("Dataset")
    ax.set_ylim(bottom=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(datasets, rotation=45, ha="right")
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.legend()

    mean_t3 = mean_metrics(t3, datasets)
    mean_actual = mean_metrics(updated_actual_cards, datasets)
    mean_est = mean_metrics(updated_est_cards, datasets)

    table_rows = [
        [f"{mean_t3[m]:.4f}" for m in METRICS],
        [f"{mean_actual[m]:.4f}" for m in METRICS],
        [f"{mean_est[m]:.4f}" for m in METRICS],
    ]
    row_labels = [
        "force umbra mapping",
        "postgres feature vector (act cards)",
        "postgres feature vector (est cards)",
    ]
    table = ax.table(
        cellText=table_rows,
        rowLabels=row_labels,
        colLabels=METRICS,
        cellLoc="center",
        rowLoc="center",
        bbox=[0.14, -0.78, 0.80, 0.38],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    # Reserve more bottom margin to keep the table fully visible and separated.
    fig.subplots_adjust(left=0.06, right=0.98, top=0.9, bottom=0.5)
    fig.savefig(args.output, dpi=220)
    print(f"Saved plot: {args.output}")


if __name__ == "__main__":
    main()
