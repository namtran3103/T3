"""
Map zero-shot RAW plan JSON (e.g. from zero-shot-data/runs/raw) to T3 format.

Raw files contain query_list with analyze_plans: PostgreSQL EXPLAIN (ANALYZE) text output.
This module:
- Parses the text plan into a tree (indentation + "->" denote structure)
- Maps PG operator names to zeroshot/T3 (same as zeroshot_to_t3)
- Extracts cardinalities (est_card, act_card), costs, widths, actual times.
  Values are stored as in zero-shot-cost-estimation (raw PG numbers, no loops multiplication).
  plan_runtime is taken from "Execution time: X ms" when present, else root act_time.
- Computes overall_selectivity and input cardinality for scans from "Rows Removed by Filter"
- Builds zeroshot-style plan (plan_parameters, children, plan_runtime) then uses zeroshot_to_t3
  for pipeline breakers, T3 plan shape, and feature generation.

Use as many queries as possible: every query with valid analyze_plans and parseable tree is used.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from src.zeroshot.operator_stages_patch import apply_zeroshot_operator_stages_patch
from src.zeroshot.zeroshot_to_t3 import zeroshot_plan_to_t3

apply_zeroshot_operator_stages_patch()

# Regex for plan node lines (PG EXPLAIN ANALYZE text)
# Root: "Finalize Aggregate  (cost=358308.32..358308.33 rows=1 width=8) (actual time=2057.058..2076.009 rows=1 loops=1)"
# Child: "  ->  Gather  (cost=358308.10..358308.31 rows=2 width=8) (actual time=2029.281..2076.000 rows=3 loops=1)"
_RE_COST = re.compile(r"\(cost=([\d.]+)\.\.([\d.]+)\s+rows=(\d+)\s+width=(\d+)\)")
_RE_ACTUAL = re.compile(r"\(actual time=([\d.]+)\.\.([\d.]+)\s+rows=(\d+)\s+loops=(\d+)\)")
_RE_ROWS_REMOVED = re.compile(r"Rows Removed by Filter:\s*(\d+)")
_RE_EXECUTION_TIME = re.compile(r"execution time:\s*([\d.]+)\s*ms", re.I)


def _flatten_plan_lines(analyze_plans: Any) -> list[str]:
    """Flatten analyze_plans (list of list of strings) to a single list of lines."""
    if not analyze_plans or not isinstance(analyze_plans, list):
        return []
    lines: list[str] = []
    for item in analyze_plans:
        if isinstance(item, list):
            for sub in item:
                if isinstance(sub, str):
                    lines.append(sub)
                else:
                    lines.append(str(sub))
        elif isinstance(item, str):
            lines.append(item)
        else:
            lines.append(str(item))
    return lines


def _parse_node_line(line: str) -> Optional[dict[str, Any]]:
    """
    Parse a single plan node line. Returns None if not a plan node (e.g. "Hash Cond:", "Filter:").
    Returns dict with: indent, op_name, est_startup_cost, est_cost, est_card, est_width,
    act_startup_cost, act_time, act_card, loops.
    """
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)

    # Child line: "  ->  Operator Name  (cost=...)(actual time=...)"
    if stripped.startswith("-> "):
        op_part = stripped[3:].strip()  # after "-> "
    else:
        # Root: "Operator Name  (cost=...)(actual time=...)"
        op_part = stripped

    # Operator name: everything before "  (" or " ("
    paren = op_part.find("  (")
    if paren < 0:
        paren = op_part.find(" (")
    if paren < 0:
        return None
    op_name = op_part[:paren].strip()
    if not op_name:
        return None

    rest = op_part[paren:]
    cost_match = _RE_COST.search(rest)
    actual_match = _RE_ACTUAL.search(rest)

    est_startup = est_cost = est_card = est_width = None
    if cost_match:
        est_startup = float(cost_match.group(1))
        est_cost = float(cost_match.group(2))
        est_card = float(cost_match.group(3))
        est_width = float(cost_match.group(4))

    act_startup = act_time = act_card = loops = None
    if actual_match:
        act_startup = float(actual_match.group(1))
        act_time = float(actual_match.group(2))
        act_card = float(actual_match.group(3))
        loops = int(actual_match.group(4))
        # Match zero-shot-cost-estimation: store raw PG values (no * loops). Their actual_regex
        # does not capture loops; parsed_plans therefore have act_card/act_time as printed.

    # Require at least cost or actual so we have something
    if cost_match is None and actual_match is None:
        return None

    return {
        "indent": indent,
        "op_name": op_name,
        "est_startup_cost": est_startup,
        "est_cost": est_cost,
        "est_card": est_card if est_card is not None else 1.0,
        "est_width": est_width if est_width is not None else 8.0,
        "act_startup_cost": act_startup,
        "act_time": act_time,
        "act_card": act_card,
        "act_children_card": None,
        "loops": loops,
        "rows_removed_by_filter": None,
    }


def _build_tree_from_lines(lines: list[str]) -> Optional[dict]:
    """
    Parse lines into a list of node infos (with line index), then build tree.
    Returns zeroshot-style plan: { plan_parameters, children, plan_runtime } or None.
    """
    node_infos: list[tuple[int, dict]] = []  # (line_idx, node_info)
    for idx, line in enumerate(lines):
        parsed = _parse_node_line(line)
        if parsed is not None:
            # Look ahead for Rows Removed by Filter (for scan nodes)
            op = (parsed.get("op_name") or "").strip()
            if op in ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan"):
                for j in range(idx + 1, min(idx + 6, len(lines))):
                    m = _RE_ROWS_REMOVED.search(lines[j])
                    if m:
                        parsed["rows_removed_by_filter"] = int(m.group(1))
                        break
            node_infos.append((idx, parsed))

    if not node_infos:
        return None

    # Build tree from indent: stack of (indent, node_dict). Node dict has plan_parameters, children.
    # Zeroshot node: { plan_parameters: {...}, children: [ ... ] }
    def make_zs_node(info: dict) -> dict:
        p = info
        est_card = p.get("est_card") or 1.0
        act_card = p.get("act_card")
        if act_card is None:
            act_card = est_card
        rows_removed = p.get("rows_removed_by_filter")
        input_card = None
        overall_selectivity = None
        if rows_removed is not None and act_card is not None:
            input_card = act_card + rows_removed
            if input_card > 0:
                overall_selectivity = act_card / input_card

        plan_params = {
            "op_name": p.get("op_name", ""),
            "est_startup_cost": p.get("est_startup_cost"),
            "est_cost": p.get("est_cost"),
            "est_card": est_card,
            "est_width": max(8.0, p.get("est_width") or 8.0),
            "act_startup_cost": p.get("act_startup_cost"),
            "act_time": p.get("act_time"),
            "act_card": act_card,
            "est_children_card": p.get("est_children_card"),
            "act_children_card": p.get("act_children_card"),
        }
        if input_card is not None:
            plan_params["input_cardinality"] = input_card
        if overall_selectivity is not None:
            plan_params["overall_selectivity"] = overall_selectivity
        return {"plan_parameters": plan_params, "children": []}

    stack: list[tuple[int, dict]] = []  # (indent, zs_node)
    root = None
    for _line_idx, info in node_infos:
        zs_node = make_zs_node(info)
        indent = info["indent"]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            root = zs_node
            stack.append((indent, zs_node))
            continue
        parent = stack[-1][1]
        parent["children"].append(zs_node)
        stack.append((indent, zs_node))

    if root is None:
        return None

    # plan_runtime (ms): match zero-shot-cost-estimation — use "Execution time: X ms" when present.
    root["plan_runtime"] = None
    for line in lines:
        m = _RE_EXECUTION_TIME.search(line)
        if m:
            root["plan_runtime"] = float(m.group(1))
            break
    if root["plan_runtime"] is None:
        act_time = root.get("plan_parameters", {}).get("act_time")
        if act_time is not None and act_time > 0:
            root["plan_runtime"] = act_time

    return root


def raw_plan_to_zeroshot(raw_plan_lines: list[str]) -> Optional[dict]:
    """
    Convert raw EXPLAIN (ANALYZE) text lines to a zeroshot-style plan (plan_parameters, children, plan_runtime).
    Returns None if parsing fails or no plan node found.
    """
    if not raw_plan_lines:
        return None
    return _build_tree_from_lines(raw_plan_lines)


def raw_plan_to_t3(
    raw_plan_lines: list[str],
    use_actual_card: bool = True,
) -> Optional[dict]:
    """
    Convert raw EXPLAIN (ANALYZE) text lines to T3 format (plan, ius, analyzePlanPipelines, plan_runtime_seconds).
    Returns None if parsing or conversion fails.
    """
    zs_plan = raw_plan_to_zeroshot(raw_plan_lines)
    if zs_plan is None:
        return None
    try:
        return zeroshot_plan_to_t3(zs_plan, use_actual_card=use_actual_card)
    except Exception:
        return None


def load_raw_json(path: str | Path) -> dict:
    """Load raw zero-shot JSON (query_list, database_stats, etc.)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_all_raw_jsons(root_dir: str | Path) -> list[Path]:
    """Collect all .json files under root_dir (e.g. raw directory)."""
    root = Path(root_dir)
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.json"))


def convert_raw_file_to_t3(
    json_path: str | Path,
    use_actual_card: bool = True,
) -> list[dict]:
    """
    Load a raw zero-shot JSON and convert each query that has analyze_plans to T3 format.
    Returns list of T3 plan dicts. Queries without analyze_plans or with parse failure are skipped.
    """
    data = load_raw_json(json_path)
    query_list = data.get("query_list", [])
    results: list[dict] = []
    for q in query_list:
        ap = q.get("analyze_plans")
        if not ap:
            continue
        lines = _flatten_plan_lines(ap)
        if not lines:
            continue
        t3 = raw_plan_to_t3(lines, use_actual_card=use_actual_card)
        if t3 is not None and t3.get("plan_runtime_seconds") is not None and t3["plan_runtime_seconds"] > 0:
            results.append(t3)
    return results


def get_minimal_database():
    """Return minimal Database for raw/zeroshot plans (no schema). Same as zeroshot_to_t3."""
    from src.database import Database
    from src.schemata import Schema, Table

    table = Table("unknown", {}, 1_000_000)
    schema = Schema(tables={"unknown": table}, join_columns={}, name="zeroshot")
    return Database(schema, None)
