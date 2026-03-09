#!/usr/bin/env python3
"""Compare two holdout implementations: alter Stand (lines 143-163) vs neuer Stand (lines 271-291).
Generates a markdown report with:
- Grouped bar chart (p50 by dataset, both implementations side by side)
- Two median tables (one per implementation)

Usage:
  python -m holdout_compare_stand
  python -m holdout_compare_stand --input holdout.txt --output holdout_compare_stand.md
"""

import re
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False

ROOT = Path(__file__).resolve().parent
HOLDOUT_FILE = ROOT / "holdout.txt"
OUTPUT_MD = ROOT / "holdout_compare_stand.md"
CHART_FILENAME = "holdout_compare_stand_p50_bars.png"

# Pattern: Test set (name, N queries): q-error avg=X p50=Y p90=Z min=M max=Max
LINE_PATTERN = re.compile(
    r"Test set \((\w+),\s*(\d+)\s*queries\):\s*q-error\s+"
    r"avg=([\d.]+)\s+p50=([\d.]+)\s+p90=([\d.]+)\s+"
    r"min=([\d.]+)\s+max=([\d.]+)"
)


def parse_holdout_slice(path: Path, start: int, end: int) -> list[dict]:
    """Parse holdout file lines [start, end] (1-based inclusive) into list of row dicts."""
    lines = path.read_text().strip().splitlines()
    rows = []
    for i in range(start - 1, min(end, len(lines))):
        line = lines[i].strip()
        m = LINE_PATTERN.match(line)
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


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2.0 if n % 2 == 0 else s[mid]


def _medians(rows: list[dict]) -> dict[str, float]:
    return {
        "avg": _median([r["avg"] for r in rows]),
        "p50": _median([r["p50"] for r in rows]),
        "p90": _median([r["p90"] for r in rows]),
        "min": _median([r["min"] for r in rows]),
        "max": _median([r["max"] for r in rows]),
    }


def format_num(x: float) -> str:
    return f"{x:.4f}"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Compare alter Stand vs neuer Stand holdout results.")
    ap.add_argument("--input", type=Path, default=HOLDOUT_FILE, help="holdout.txt path")
    ap.add_argument("--output", type=Path, default=OUTPUT_MD, help="Output markdown path")
    ap.add_argument("--alter-start", type=int, default=143, help="Alter Stand: first line (1-based)")
    ap.add_argument("--alter-end", type=int, default=163, help="Alter Stand: last line (1-based)")
    ap.add_argument("--neuer-start", type=int, default=271, help="Neuer Stand: first line (1-based)")
    ap.add_argument("--neuer-end", type=int, default=291, help="Neuer Stand: last line (1-based)")
    args = ap.parse_args()

    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    alter_rows = parse_holdout_slice(input_path, args.alter_start, args.alter_end)
    neuer_rows = parse_holdout_slice(input_path, args.neuer_start, args.neuer_end)

    if not alter_rows or not neuer_rows:
        print("Could not parse one or both sections from", input_path)
        return

    # Build dataset order (use alter as reference; both should have same datasets)
    datasets = [r["dataset"] for r in alter_rows]
    alter_by_ds = {r["dataset"]: r for r in alter_rows}
    neuer_by_ds = {r["dataset"]: r for r in neuer_rows}

    alter_p50 = [alter_by_ds[d]["p50"] for d in datasets]
    neuer_p50 = [neuer_by_ds[d]["p50"] for d in datasets]

    med_alter = _medians(alter_rows)
    med_neuer = _medians(neuer_rows)

    md_lines = [
        "# Holdout-Vergleich: alter Stand vs neuer Stand",
        "",
        "## p50 by dataset (grouped bar chart)",
        "",
    ]

    if _HAS_MATPLOTLIB:
        n = len(datasets)
        x = list(range(n))
        width = 0.35

        fig, ax = plt.subplots(figsize=(14, 5))
        ax.bar([i - width / 2 for i in x], alter_p50, width, label="alter Stand", color="#c0392b", edgecolor="none")
        ax.bar([i + width / 2 for i in x], neuer_p50, width, label="neuer Stand", color="#2980b9", edgecolor="none")

        ax.set_ylabel("p50")
        ax.set_title("Q-error p50 by dataset — alter Stand vs neuer Stand")
        ax.set_xticks(x)
        ax.set_xticklabels(datasets, rotation=45, ha="right")
        ax.legend()
        ax.set_ylim(1, None)
        fig.tight_layout()
        chart_path = output_path.parent / CHART_FILENAME
        fig.savefig(chart_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        md_lines.append(f"![p50 comparison]({CHART_FILENAME})")
    else:
        md_lines.append("*(Install matplotlib to generate the grouped bar chart.)*")

    md_lines.extend([
        "",
        "## Medians (over datasets)",
        "",
        "### alter Stand",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| **avg** | {format_num(med_alter['avg'])} |",
        f"| **p50** | {format_num(med_alter['p50'])} |",
        f"| **p90** | {format_num(med_alter['p90'])} |",
        f"| **min** | {format_num(med_alter['min'])} |",
        f"| **max** | {format_num(med_alter['max'])} |",
        "",
        "### neuer Stand",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| **avg** | {format_num(med_neuer['avg'])} |",
        f"| **p50** | {format_num(med_neuer['p50'])} |",
        f"| **p90** | {format_num(med_neuer['p90'])} |",
        f"| **min** | {format_num(med_neuer['min'])} |",
        f"| **max** | {format_num(med_neuer['max'])} |",
        "",
    ])

    output_path.write_text("\n".join(md_lines), encoding="utf-8")
    print("Wrote", output_path)


if __name__ == "__main__":
    main()
