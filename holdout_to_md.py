#!/usr/bin/env python3
"""Generate a markdown report from holdout result files with q-error results and averages.

Supports single-block or grouped input. Grouped input uses lines like:
  ---all enriched
  Test set (accidents, 14999 queries): q-error avg=... p50=... ...
  ---all non enriched
  Test set (...): ...

Optional --start-line / --end-line restrict parsing to a line range (e.g. 53-99).
For each group: results table, p50 bar chart, and averages (avg, p50, p90, min, max).
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

HOLDOUT_FILE = Path(__file__).parent / "holdout.txt"
OUTPUT_MD = Path(__file__).parent / "holdout_results.md"

# Pattern: Test set (name, N queries): q-error avg=X p50=Y p90=Z min=M max=Max
LINE_PATTERN = re.compile(
    r"Test set \((\w+),\s*(\d+)\s*queries\):\s*q-error\s+"
    r"avg=([\d.]+)\s+p50=([\d.]+)\s+p90=([\d.]+)\s+"
    r"min=([\d.]+)\s+max=([\d.]+)"
)
GROUP_HEADER = re.compile(r"^---\s*(.+)$")


def _slug(s: str) -> str:
    """Turn group name into a safe filename stem (e.g. 'all enriched' -> 'all_enriched')."""
    return re.sub(r"\s+", "_", s.strip()).lower()


def parse_holdout_lines(lines: list[str]) -> list[dict]:
    """Parse 'Test set (...)' lines into row dicts."""
    rows = []
    for line in lines:
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


def parse_holdout_groups(path: Path, start_line: int | None, end_line: int | None) -> list[tuple[str, list[dict]]]:
    """Parse file into groups. Each group: (group_name, list of row dicts)."""
    all_lines = path.read_text().strip().splitlines()
    if start_line is not None or end_line is not None:
        one_indexed = 1
        start = (start_line or 1) - one_indexed
        end = (end_line or len(all_lines)) if end_line is not None else len(all_lines)
        all_lines = all_lines[start:end]
    groups: list[tuple[str, list[dict]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for line in all_lines:
        g = GROUP_HEADER.match(line.strip())
        if g:
            if current_name is not None:
                rows = parse_holdout_lines(current_lines)
                if rows:
                    groups.append((current_name, rows))
            current_name = g.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_name is not None:
        rows = parse_holdout_lines(current_lines)
        if rows:
            groups.append((current_name, rows))
    return groups


def format_num(x: float) -> str:
    return f"{x:.4f}"


def _averages(rows: list[dict]) -> dict[str, float]:
    n = len(rows)
    return {
        "avg": sum(r["avg"] for r in rows) / n,
        "p50": sum(r["p50"] for r in rows) / n,
        "p90": sum(r["p90"] for r in rows) / n,
        "min": sum(r["min"] for r in rows) / n,
        "max": sum(r["max"] for r in rows) / n,
    }


def _write_bar_chart(rows: list[dict], out_path: Path, title_suffix: str) -> str:
    """Save p50 bar chart; return markdown image line (filename only)."""
    p50_vals = [r["p50"] for r in rows]
    if _HAS_MATPLOTLIB:
        names = [r["dataset"] for r in rows]
        fig, ax = plt.subplots(figsize=(14, 5))
        x = range(len(names))
        ax.bar(x, p50_vals, color="#c0392b", width=0.5, edgecolor="none")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_ylabel("p50")
        ax.set_title(f"Q-error p50 by dataset — {title_suffix}")
        ax.set_ylim(1, None)
        fig.tight_layout()
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return f"![p50 by dataset — {title_suffix}]({out_path.name})"
    p50_max = max(p50_vals)
    y_max = max(round(p50_max) + 1, 2)
    x_labels = ", ".join(f'"{r["dataset"]}"' for r in rows)
    p50_str = ", ".join(format_num(v) for v in p50_vals)
    return (
        "```mermaid\nxychart-beta\n"
        f'    title "Q-error p50 by dataset — {title_suffix}"\n'
        f"    x-axis [{x_labels}]\n"
        f'    y-axis "p50" 0 --> {y_max}\n'
        f"    bar [{p50_str}]\n```"
    )


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Generate markdown report from holdout result file (single or grouped).")
    ap.add_argument("--input", type=Path, default=None, help="Input file (default: holdout.txt).")
    ap.add_argument("--start-line", type=int, default=None, help="First line to parse (1-based).")
    ap.add_argument("--end-line", type=int, default=None, help="Last line to parse (1-based).")
    args = ap.parse_args()
    input_path = args.input if args.input is not None else HOLDOUT_FILE
    if not input_path.is_absolute():
        input_path = Path(__file__).parent / input_path
    parent = input_path.parent
    base = input_path.stem
    output_md = parent / f"{base}_results.md"

    groups = parse_holdout_groups(input_path, args.start_line, args.end_line)
    if not groups:
        print("No groups parsed from", input_path)
        return

    md_lines = [
        "# Holdout Q-Error Results (grouped)",
        "",
    ]

    for group_name, rows in groups:
        slug = _slug(group_name)
        total_queries = sum(r["queries"] for r in rows)
        n = len(rows)
        avgs = _averages(rows)
        bar_path = parent / f"{base}_{slug}_p50_bars.png"

        md_lines.extend([
            f"## {group_name}",
            "",
            f"**Datasets:** {n}  |  **Total queries:** {total_queries:,}",
            "",
            "### Results by dataset",
            "",
            "| Dataset | Queries | avg | p50 | p90 | min | max |",
            "|---------|--------:|----:|----:|----:|----:|----:|",
        ])
        for r in rows:
            md_lines.append(
                f"| {r['dataset']} | {r['queries']:,} | {format_num(r['avg'])} | "
                f"{format_num(r['p50'])} | {format_num(r['p90'])} | "
                f"{format_num(r['min'])} | {format_num(r['max'])} |"
            )

        chart_md = _write_bar_chart(rows, bar_path, group_name)
        md_lines.extend([
            "",
            "### p50 by dataset",
            "",
            chart_md,
            "",
            "### Averages (over datasets)",
            "",
            "| Metric | Value |",
            "|--------|------:|",
            f"| **avg** | {format_num(avgs['avg'])} |",
            f"| **p50** | {format_num(avgs['p50'])} |",
            f"| **p90** | {format_num(avgs['p90'])} |",
            f"| **min** | {format_num(avgs['min'])} |",
            f"| **max** | {format_num(avgs['max'])} |",
            "",
        ])

    output_md.write_text("\n".join(md_lines), encoding="utf-8")
    print("Wrote", output_md)


if __name__ == "__main__":
    main()
