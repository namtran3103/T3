#!/usr/bin/env python3
"""Plot Median Q-Error grouped bar chart (paper style) with T3 holdout p50 added.

Reads p50 from holdout.txt (lines 112-132) and adds them as a fourth series.
The first three series (Scaled Optimizer Costs Postgres, Zero-Shot DeepDB Est.,
Zero-Shot Exact Cardinalities) use placeholder values matching the paper figure;
pass --paper-csv PATH to override with real data (CSV with columns: dataset, postgres, zeroshot_deepdb, zeroshot_exact).
"""

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Chart x-axis order and display names (20 datasets, as in the paper figure)
CHART_DATASETS = [
    "Accidents", "Airline", "Baseball", "Basketball", "Carcinogenesis", "Consumer",
    "Credit", "Employee", "Fhnk", "Financial", "Geneea", "Genome", "Hepatitis",
    "IMDB", "Movielens", "SSB", "Seznam", "TPC-H", "Tournament", "Walmart",
]


def chart_name_to_holdout_key(name: str) -> str:
    """Map chart display name to holdout.txt dataset key (lowercase, hyphen -> underscore)."""
    key = name.lower().replace("-", "_")
    return key


def parse_holdout_p50(lines: list[str]) -> dict[str, float]:
    """Parse 'Test set (name, N queries): q-error ... p50=X ...' lines; return dict name -> p50."""
    pattern = re.compile(
        r"Test set \((\w+),\s*\d+\s*queries\):\s*q-error\s+"
        r"avg=[\d.]+\s+p50=([\d.]+)\s+"
    )
    out = {}
    for line in lines:
        m = pattern.search(line.strip())
        if m:
            out[m.group(1).lower()] = float(m.group(2))
    return out


def load_holdout_p50(holdout_path: Path, start_line: int, end_line: int) -> dict[str, float]:
    raw = holdout_path.read_text().splitlines()
    # 1-based line range
    selected = raw[start_line - 1 : end_line]
    return parse_holdout_p50(selected)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Plot Median Q-Error with T3 holdout p50.")
    ap.add_argument("--holdout", type=Path, default=Path(__file__).parent / "holdout.txt")
    ap.add_argument("--start-line", type=int, default=112)
    ap.add_argument("--end-line", type=int, default=132)
    ap.add_argument("--paper-csv", type=Path, default=None,
                    help="Optional CSV: dataset,postgres,zeroshot_deepdb,zeroshot_exact (header row)")
    ap.add_argument("--t3-only", action="store_true",
                    help="Plot only T3 holdout p50 (same x-axis order for overlay on paper figure)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "median_qerror_with_holdout.png")
    args = ap.parse_args()

    # Load T3 holdout p50
    p50_by_key = load_holdout_p50(args.holdout, args.start_line, args.end_line)

    # Build p50 list for chart order (use IMDB from 'imdb', not 'imdb_full')
    holdout_p50 = []
    for name in CHART_DATASETS:
        key = chart_name_to_holdout_key(name)
        if key in p50_by_key:
            holdout_p50.append(p50_by_key[key])
        elif key == "imdb_full":
            holdout_p50.append(np.nan)
        else:
            # try without _full
            holdout_p50.append(p50_by_key.get(key, np.nan))
    holdout_p50 = np.array(holdout_p50)

    # Placeholder data for the paper's 3 series (approximate from figure; use --paper-csv for real data)
    n = len(CHART_DATASETS)
    postgres = np.array([8.5, 1.2, 7.5, 3.5, 3.3, 2.2, 3.2, 5.9, 4.1, 7.9, 4.6, 5.3, 3.6, 3.7, 4.7, 2.2, 5.7, 2.8, 5.3, 5.6])  # brown, high
    zeroshot_deepdb = np.array([1.4, 1.3, 1.4, 1.2, 1.5, 1.3, 1.4, 1.5, 1.4, 1.4, 1.5, 1.4, 1.5, 1.4, 1.5, 1.3, 1.4, 1.5, 1.4, 1.5])  # green
    zeroshot_exact = zeroshot_deepdb - 0.01  # blue, very similar

    if args.paper_csv and args.paper_csv.exists():
        import csv
        with open(args.paper_csv) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        key_to_row = {r["dataset"].strip().lower().replace("-", "_"): r for r in rows}
        postgres = np.array([float(key_to_row.get(chart_name_to_holdout_key(n), {}).get("postgres", np.nan)) for n in CHART_DATASETS])
        zeroshot_deepdb = np.array([float(key_to_row.get(chart_name_to_holdout_key(n), {}).get("zeroshot_deepdb", np.nan)) for n in CHART_DATASETS])
        zeroshot_exact = np.array([float(key_to_row.get(chart_name_to_holdout_key(n), {}).get("zeroshot_exact", np.nan)) for n in CHART_DATASETS])

    # Plot
    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(n)
    width = 0.2 if not args.t3_only else 0.5

    if not args.t3_only:
        ax.bar(x - 1.5 * width, postgres, width, label="Scaled Optimizer Costs (Postgres)", color="#8B4513", edgecolor="black", linewidth=0.5)
        ax.bar(x - 0.5 * width, zeroshot_deepdb, width, label="Zero-Shot (DeepDB Est.)", color="#2ecc71", edgecolor="black", linewidth=0.5)
        ax.bar(x + 0.5 * width, zeroshot_exact, width, label="Zero-Shot (Exact Cardinalities)", color="#3498db", edgecolor="black", linewidth=0.5)
    ax.bar(x if args.t3_only else x + 1.5 * width, holdout_p50, width, label="T3 (holdout p50)", color="#e67e22", edgecolor="black", linewidth=0.5)

    ax.set_ylabel("Median Q-Error")
    ax.set_xticks(x)
    ax.set_xticklabels(CHART_DATASETS, rotation=45, ha="right")
    ax.set_ylim(0, None)
    ax.legend(loc="upper right", ncol=2, fontsize=8)
    ax.set_title("Median Q-Error")
    fig.tight_layout()
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved", args.out)


if __name__ == "__main__":
    main()
