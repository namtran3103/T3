#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


LINE_RE = re.compile(
    r"^(?P<query>[^:]+):\s+pred=[0-9.]+s\s+actual=[0-9.]+s\s+q_error=(?P<qerr>[0-9.]+)\s*$"
)


def parse_qerrors(file_path: Path):
    items = []
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if m:
            items.append((m.group("query"), float(m.group("qerr"))))

    if not items:
        raise ValueError(f"No query lines with q_error found in {file_path}")

    return items


def compute_stats(values):
    arr = np.array(values, dtype=float)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "avg": float(np.mean(arr)),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Plot q-error bars sorted from lowest to highest and include stats table."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="job_zero_t3_results_est_cards_0322.txt",
        help="Path to results txt file (default: job_zero_t3_results_est_cards_0322.txt)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output image path (default: <input_stem>_qerror_sorted.png)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    data = parse_qerrors(input_path)
    sorted_data = sorted(data, key=lambda x: x[1])
    qerrs = [v for _, v in sorted_data]
    stats = compute_stats(qerrs)

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_qerror_sorted.png")
    )

    fig, ax = plt.subplots(figsize=(16, 8))
    x = np.arange(1, len(qerrs) + 1)
    ax.bar(x, qerrs, color="#4C78A8", width=0.85, align="center")
    ax.set_title(f"Q-error per Query (sorted ascending) - {input_path.name}")
    ax.set_xlabel("Query index after sorting by q-error (1..N)")
    ax.set_ylabel("Q-error")
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_xlim(0.5, len(qerrs) + 0.5)

    # Use numeric x-axis labels 1..N; show sparse ticks for readability.
    step = max(1, len(qerrs) // 12)
    tick_positions = np.arange(1, len(qerrs) + 1, step)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([str(i) for i in tick_positions], rotation=0)

    table_labels = ["p50", "p75", "p90", "min", "max", "avg"]
    table_values = [f"{stats[k]:.4f}" for k in table_labels]
    table = ax.table(
        cellText=[table_values],
        colLabels=table_labels,
        cellLoc="center",
        colLoc="center",
        bbox=[0.03, 0.78, 0.46, 0.16],  # [left, bottom, width, height] in axes coords
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    plt.tight_layout()
    fig.savefig(output_path, dpi=220)
    print(f"Saved plot: {output_path}")


if __name__ == "__main__":
    main()
