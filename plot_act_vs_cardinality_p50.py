#!/usr/bin/env python3
"""Plot act (full run with act cards...) vs cardinality estimates testing p50 in one grouped bar chart. Saves JPG."""

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
HOLDOUT_FILE = SCRIPT_DIR / "holdout.txt"
OUT_JPG = SCRIPT_DIR / "act_vs_cardinality_p50.jpg"

LINE_PATTERN = re.compile(
    r"Test set \((\w+),\s*(\d+)\s*queries\):\s*q-error\s+"
    r"avg=([\d.]+)\s+p50=([\d.]+)\s+p90=([\d.]+)\s+"
    r"min=([\d.]+)\s+max=([\d.]+)"
)


def parse_block(path: Path, start_line: int, end_line: int) -> list[tuple[str, float]]:
    """Return list of (dataset, p50) in file order (1-based line numbers)."""
    lines = path.read_text().strip().splitlines()
    one_indexed = 1
    start = start_line - one_indexed
    end = end_line
    rows = []
    for line in lines[start:end]:
        line = line.strip()
        if not line:
            continue
        m = LINE_PATTERN.match(line)
        if m:
            rows.append((m.group(1), float(m.group(4))))
    return rows


def main() -> None:
    # act: full run with act cards, rm startswith and between, large vector (holdout.txt 271-291)
    act = dict(parse_block(HOLDOUT_FILE, 271, 292))
    # cardinality estimates testing (holdout.txt 298-318)
    card = dict(parse_block(HOLDOUT_FILE, 298, 319))

    datasets = list(act.keys())
    assert set(datasets) == set(card.keys()), "Dataset sets must match"
    p50_act = [act[d] for d in datasets]
    p50_card = [card[d] for d in datasets]

    n = len(datasets)
    x = np.arange(n)
    width = 0.35

    fig, ax = plt.subplots(figsize=(16, 6))
    bars1 = ax.bar(x - width / 2, p50_act, width, label="act (full run with act cards, …)", color="#c0392b", edgecolor="none")
    bars2 = ax.bar(x + width / 2, p50_card, width, label="cardinality estimates", color="#2980b9", edgecolor="none")

    ax.set_ylabel("Q-error p50")
    ax.set_xticks(x)
    ax.set_xticklabels(datasets, rotation=45, ha="right")
    ax.set_title("Holdout p50: act vs cardinality estimates")
    ax.legend(loc="upper right")
    ax.set_ylim(1, None)
    ax.axhline(y=1, color="gray", linestyle="--", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(OUT_JPG, dpi=150, format="jpg", bbox_inches="tight")
    plt.close(fig)
    print("Wrote", OUT_JPG)


if __name__ == "__main__":
    main()
