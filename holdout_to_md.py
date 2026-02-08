#!/usr/bin/env python3
"""Generate a markdown report from holdout.txt with q-error results and averages."""

import re
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False

HOLDOUT_FILE = Path(__file__).parent / "holdout.txt"
OUTPUT_MD = Path(__file__).parent / "holdout_results.md"
BAR_CHART_PATH = Path(__file__).parent / "holdout_p50_bars.png"

# Pattern: Test set (name, N queries): q-error avg=X p50=Y p90=Z min=M max=Max
LINE_PATTERN = re.compile(
    r"Test set \((\w+),\s*(\d+)\s*queries\):\s*q-error\s+"
    r"avg=([\d.]+)\s+p50=([\d.]+)\s+p90=([\d.]+)\s+"
    r"min=([\d.]+)\s+max=([\d.]+)"
)


def parse_holdout(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line:
            continue
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


def format_num(x: float) -> str:
    return f"{x:.4f}"


def main() -> None:
    rows = parse_holdout(HOLDOUT_FILE)
    if not rows:
        print("No data parsed from", HOLDOUT_FILE)
        return

    total_queries = sum(r["queries"] for r in rows)
    n = len(rows)

    avg_avg = sum(r["avg"] for r in rows) / n
    avg_p50 = sum(r["p50"] for r in rows) / n
    avg_p90 = sum(r["p90"] for r in rows) / n
    avg_min = sum(r["min"] for r in rows) / n
    avg_max = sum(r["max"] for r in rows) / n

    md_lines = [
        "# Holdout Q-Error Results",
        "",
        f"**Datasets:** {n}  |  **Total queries:** {total_queries:,}",
        "",
        "## Results by dataset",
        "",
        "| Dataset | Queries | avg | p50 | p90 | min | max |",
        "|---------|--------:|----:|----:|----:|----:|----:|",
    ]

    for r in rows:
        md_lines.append(
            f"| {r['dataset']} | {r['queries']:,} | {format_num(r['avg'])} | "
            f"{format_num(r['p50'])} | {format_num(r['p90'])} | "
            f"{format_num(r['min'])} | {format_num(r['max'])} |"
        )

    # Bar chart (p50): red bars, spaced apart
    p50_vals = [r["p50"] for r in rows]
    if _HAS_MATPLOTLIB:
        names = [r["dataset"] for r in rows]
        fig, ax = plt.subplots(figsize=(14, 5))
        x = range(len(names))
        ax.bar(x, p50_vals, color="#c0392b", width=0.5, edgecolor="none")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_ylabel("p50")
        ax.set_title("Q-error p50 by dataset")
        ax.set_ylim(0, None)
        fig.tight_layout()
        fig.savefig(BAR_CHART_PATH, dpi=120, bbox_inches="tight")
        plt.close(fig)
        chart_md = [f"![p50 by dataset]({BAR_CHART_PATH.name})"]
    else:
        p50_max = max(p50_vals)
        y_max = max(round(p50_max) + 1, 2)
        x_labels = ", ".join(f'"{r["dataset"]}"' for r in rows)
        p50_str = ", ".join(format_num(v) for v in p50_vals)
        chart_md = [
            "```mermaid",
            "xychart-beta",
            "    title \"Q-error p50 by dataset\"",
            f"    x-axis [{x_labels}]",
            f"    y-axis \"p50\" 0 --> {y_max}",
            f"    bar [{p50_str}]",
            "```",
        ]

    md_lines.extend([
        "",
        "## p50 by dataset",
        "",
        *chart_md,
        "",
        "## Averages (over datasets)",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| **avg** | {format_num(avg_avg)} |",
        f"| **p50** | {format_num(avg_p50)} |",
        f"| **p90** | {format_num(avg_p90)} |",
        f"| **min** | {format_num(avg_min)} |",
        f"| **max** | {format_num(avg_max)} |",
        "",
    ])

    OUTPUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print("Wrote", OUTPUT_MD)


if __name__ == "__main__":
    main()
