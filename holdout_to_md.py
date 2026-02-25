#!/usr/bin/env python3
"""Generate a markdown report from holdout result files with q-error results and averages.

Supports single-block or grouped input. Grouped input uses lines like:
  ---all enriched
  Test set (accidents, 14999 queries): q-error avg=... p50=... ...
  ---all non enriched
  Test set (...): ...

Optional --start-line / --end-line restrict parsing to a line range (e.g. 53-99).
For each group: results table, p50 bar chart, and medians (over datasets) for avg, p50, p90, min, max.
Optional --jh FILE (with --jh-start-line / --jh-end-line) adds a third section from JH-format lines (holdout=... n=...).
Optional --jh2 FILE (with --jh2-start-line / --jh2-end-line / --jh2-title) adds a fourth section from a second JH block.
Optional --extra-start-line / --extra-end-line / --extra-title add a section from an extra line range in the main input file.
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
# Pattern: holdout=NAME n=N min= max= avg= p50= p75= p90=
LINE_PATTERN_JH = re.compile(
    r"holdout=(\w+)\s+n=(\d+)\s+min=([\d.]+)\s+max=([\d.]+)\s+avg=([\d.]+)\s+"
    r"p50=([\d.]+)\s+p75=([\d.]+)\s+p90=([\d.]+)"
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


def parse_holdout_jh_lines(lines: list[str]) -> list[dict]:
    """Parse 'holdout=NAME n=N min= ... p50= ... p90= ...' lines into row dicts (same shape as parse_holdout_lines)."""
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = LINE_PATTERN_JH.match(line)
        if m:
            rows.append({
                "dataset": m.group(1),
                "queries": int(m.group(2)),
                "min": float(m.group(3)),
                "max": float(m.group(4)),
                "avg": float(m.group(5)),
                "p50": float(m.group(6)),
                "p90": float(m.group(8)),  # p75 is group 7
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


def _median(vals: list[float]) -> float:
    n = len(vals)
    if not n:
        return 0.0
    s = sorted(vals)
    mid = n // 2
    return (s[mid] + s[mid - 1]) / 2.0 if n % 2 == 0 else s[mid]


def _medians(rows: list[dict]) -> dict[str, float]:
    return {
        "avg": _median([r["avg"] for r in rows]),
        "p50": _median([r["p50"] for r in rows]),
        "p90": _median([r["p90"] for r in rows]),
        "min": _median([r["min"] for r in rows]),
        "max": _median([r["max"] for r in rows]),
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
    ap.add_argument("--output", type=Path, default=None, help="Output markdown file (default: {input_stem}_results.md).")
    ap.add_argument("--start-line", type=int, default=None, help="First line to parse (1-based).")
    ap.add_argument("--end-line", type=int, default=None, help="Last line to parse (1-based).")
    ap.add_argument("--jh", type=Path, default=None, help="Optional JH-format file for a third section (e.g. holdout_jh.txt).")
    ap.add_argument("--jh-start-line", type=int, default=None, help="First line in JH file (1-based).")
    ap.add_argument("--jh-end-line", type=int, default=None, help="Last line in JH file (1-based).")
    ap.add_argument("--jh2", type=Path, default=None, help="Optional second JH-format file for a fourth section.")
    ap.add_argument("--jh2-start-line", type=int, default=None, help="First line in JH2 file (1-based).")
    ap.add_argument("--jh2-end-line", type=int, default=None, help="Last line in JH2 file (1-based).")
    ap.add_argument("--jh2-title", type=str, default="all jh (fixed)", help="Title for the fourth section (default: all jh (fixed)).")
    ap.add_argument("--extra-start-line", type=int, default=None, help="Extra block: first line in input file (1-based).")
    ap.add_argument("--extra-end-line", type=int, default=None, help="Extra block: last line in input file (1-based).")
    ap.add_argument("--extra-title", type=str, default="full run with fix", help="Title for the extra block section.")
    args = ap.parse_args()
    input_path = args.input if args.input is not None else HOLDOUT_FILE
    if not input_path.is_absolute():
        input_path = Path(__file__).parent / input_path
    parent = input_path.parent
    base = input_path.stem
    output_md = args.output if args.output is not None else parent / f"{base}_results.md"
    if not output_md.is_absolute():
        output_md = Path(__file__).parent / output_md

    groups = parse_holdout_groups(input_path, args.start_line, args.end_line)
    if args.jh is not None:
        jh_path = args.jh if args.jh.is_absolute() else Path(__file__).parent / args.jh
        jh_lines = jh_path.read_text().strip().splitlines()
        one_indexed = 1
        start = (args.jh_start_line or 1) - one_indexed
        end = (args.jh_end_line or len(jh_lines)) if args.jh_end_line is not None else len(jh_lines)
        jh_rows = parse_holdout_jh_lines(jh_lines[start:end])
        if jh_rows:
            groups.append(("all jh", jh_rows))
    if args.jh2 is not None:
        jh2_path = args.jh2 if args.jh2.is_absolute() else Path(__file__).parent / args.jh2
        jh2_lines = jh2_path.read_text().strip().splitlines()
        one_indexed = 1
        start = (args.jh2_start_line or 1) - one_indexed
        end = (args.jh2_end_line or len(jh2_lines)) if args.jh2_end_line is not None else len(jh2_lines)
        jh2_rows = parse_holdout_jh_lines(jh2_lines[start:end])
        if jh2_rows:
            groups.append((args.jh2_title, jh2_rows))
    if args.extra_start_line is not None and args.extra_end_line is not None:
        all_input = input_path.read_text().strip().splitlines()
        one_indexed = 1
        start = args.extra_start_line - one_indexed
        end = args.extra_end_line
        extra_lines = all_input[start:end]
        extra_rows = parse_holdout_lines(extra_lines)
        if extra_rows:
            groups.append((args.extra_title, extra_rows))
    if not groups:
        print("No groups parsed from", input_path, "or JH file")
        return

    md_lines = [
        "# Holdout Q-Error Results (grouped)",
        "",
    ]

    for group_name, rows in groups:
        slug = _slug(group_name)
        total_queries = sum(r["queries"] for r in rows)
        n = len(rows)
        meds = _medians(rows)
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
            "### Medians (over datasets)",
            "",
            "| Metric | Value |",
            "|--------|------:|",
            f"| **avg** | {format_num(meds['avg'])} |",
            f"| **p50** | {format_num(meds['p50'])} |",
            f"| **p90** | {format_num(meds['p90'])} |",
            f"| **min** | {format_num(meds['min'])} |",
            f"| **max** | {format_num(meds['max'])} |",
            "",
        ])

    output_md.write_text("\n".join(md_lines), encoding="utf-8")
    print("Wrote", output_md)


if __name__ == "__main__":
    main()
