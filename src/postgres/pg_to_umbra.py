"""
Convert PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) output to Umbra-style plan
for T3 inference. Handles JOB-style plans: Seq Scan, Index Scan, Hash Join,
Nested Loop, Aggregate, Sort, Gather, Memoize, Hash, Materialize.

Pipeline breakers (materialization points, per T3 paper): Hash/IndexNL join build
sides, Sort, Aggregate, and PG Materialize. Each starts a new pipeline so
parents of a breaker are assigned to the new pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _plan_rows(pg: dict) -> float:
    return float(pg.get("Plan Rows", 1))


def _actual_rows(pg: dict) -> float:
    return float(pg.get("Actual Rows", 0)) * float(pg.get("Actual Loops", 1))


def _plan_width(pg: dict) -> float:
    return max(1, float(pg.get("Plan Width", 8)))


def _start_stop(pg: dict) -> tuple[float, float]:
    start = float(pg.get("Actual Startup Time", 0))
    total = float(pg.get("Actual Total Time", 0))
    return start, total


# Minimal PG plan used when Plans is empty so T3 never sees input/left/right as {} (avoids KeyError 'input').
_PLACEHOLDER_PG: dict = {"Node Type": "Seq Scan", "Plan Rows": 0, "Actual Rows": 0, "Relation Name": "company_name"}


def _convert_child(pg: dict | None, next_id: list, use_actual_card: bool) -> dict:
    """Convert one PG plan node or placeholder if missing."""
    return _convert_node(pg or _PLACEHOLDER_PG.copy(), next_id, use_actual_card)


def _convert_node(pg: dict, next_id: list, use_actual_card: bool) -> dict:
    """Convert one PG plan node to Umbra-style. Mutates next_id[0] for analyzePlanId."""
    if not pg or not pg.get("Node Type"):
        pg = _PLACEHOLDER_PG.copy()
    nid = next_id[0]
    next_id[0] += 1
    node_type = pg.get("Node Type", "")
    plan_rows = _plan_rows(pg)
    actual = _actual_rows(pg)
    width = _plan_width(pg)
    cardinality = actual if use_actual_card else plan_rows
    out = {
        "operator": "",
        "operatorId": nid,
        "analyzePlanId": nid,
        "cardinality": cardinality,
        "analyzePlanCardinality": actual,
        "producedIUs": [{"estimatedSize": width}],
        "restrictions": [],
        "residuals": [],
    }
    plans = pg.get("Plans", [])

    if node_type in ("Seq Scan", "Index Scan", "Index Only Scan"):
        out["operator"] = "tablescan"
        out["tablename"] = pg.get("Relation Name", "unknown")
        return out

    if node_type == "Hash Join":
        outer = plans[0] if plans else None
        inner = plans[1].get("Plans", [None])[0] if len(plans) > 1 and plans[1].get("Node Type") == "Hash" else (plans[1] if len(plans) > 1 else None)
        out["operator"] = "join"
        out["physicalOperator"] = "hashjoin"
        out["left"] = _convert_child(outer, next_id, use_actual_card)
        out["right"] = _convert_child(inner, next_id, use_actual_card)
        return out

    if node_type == "Nested Loop":
        out["operator"] = "join"
        out["physicalOperator"] = "indexnljoin"
        out["left"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
        out["right"] = _convert_child(plans[1] if len(plans) > 1 else None, next_id, use_actual_card)
        return out

    if node_type == "Aggregate":
        out["operator"] = "groupby"
        out["input"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
        return out

    if node_type == "Sort":
        out["operator"] = "sort"
        out["input"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
        return out

    if node_type == "Hash":
        out["operator"] = "temp"
        out["input"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
        return out

    if node_type == "Materialize":
        out["operator"] = "temp"
        out["pgMaterialize"] = True
        out["input"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
        return out

    if node_type in ("Gather", "Memoize"):
        out["operator"] = "select"
        out["input"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
        return out

    # Fallback: single-input pass-through
    out["operator"] = "select"
    out["input"] = _convert_child(plans[0] if plans else None, next_id, use_actual_card)
    return out


def _is_pipeline_breaker(node: dict) -> bool:
    """Operators that materialize: start a new pipeline (breaker and everything above in new pipeline)."""
    op = node.get("operator", "")
    return op in ("sort", "groupby") or (op == "temp" and node.get("pgMaterialize"))


def _assign_pipelines(
    node: dict, pipeline_by_id: dict, current_pipeline: list, next_pipeline_id: list
) -> int:
    """Assign pipeline id to each node. Returns the pipeline id this node was assigned to."""
    nid = node.get("analyzePlanId")
    if nid is None:
        return current_pipeline[0]
    op = node.get("operator", "")
    phys = node.get("physicalOperator", "")

    # Joins: node and left in current pipeline, right in new (so join is Probe in T3; Build side separate).
    if op == "join" and phys in ("hashjoin", "indexnljoin"):
        pipeline_by_id[nid] = current_pipeline[0]
        _assign_pipelines(node["left"], pipeline_by_id, current_pipeline, next_pipeline_id)
        next_pipeline_id[0] += 1
        _assign_pipelines(node["right"], pipeline_by_id, [next_pipeline_id[0]], next_pipeline_id)
        return current_pipeline[0]

    # Pipeline breakers: input stays in current, this node starts a new pipeline.
    if _is_pipeline_breaker(node):
        if "input" in node and isinstance(node["input"], dict):
            _assign_pipelines(node["input"], pipeline_by_id, current_pipeline, next_pipeline_id)
        next_pipeline_id[0] += 1
        pipeline_by_id[nid] = next_pipeline_id[0]
        return next_pipeline_id[0]

    # Unary: same pipeline as child.
    if "input" in node and isinstance(node["input"], dict):
        child_pid = _assign_pipelines(node["input"], pipeline_by_id, current_pipeline, next_pipeline_id)
        pipeline_by_id[nid] = child_pid
        return child_pid

    # Leaf or other binary: stay in current, recurse into children.
    pipeline_by_id[nid] = current_pipeline[0]
    for key in ("left", "right", "input"):
        if key in node and isinstance(node[key], dict):
            _assign_pipelines(node[key], pipeline_by_id, current_pipeline, next_pipeline_id)
    return current_pipeline[0]


def _fill_times_pg(pg_node: dict, umbra_node: dict, times_by_id: dict) -> None:
    """Store (start, total) for each Umbra node from matching PG node. Recurse in same order as convert."""
    nid = umbra_node.get("analyzePlanId")
    if nid is not None and "Actual Startup Time" in pg_node:
        start, total = _start_stop(pg_node)
        times_by_id[nid] = (start, total)
    plans = pg_node.get("Plans", [])
    idx = 0
    for key in ("left", "right", "input"):
        if key not in umbra_node or not isinstance(umbra_node[key], dict):
            continue
        if key == "right" and umbra_node.get("physicalOperator") == "hashjoin" and len(plans) > 1 and plans[1].get("Node Type") == "Hash":
            pg_child = plans[1].get("Plans", [{}])[0]
        else:
            pg_child = plans[idx] if idx < len(plans) else {}
            idx += 1
        if pg_child:
            _fill_times_pg(pg_child, umbra_node[key], times_by_id)


def pg_explain_to_umbra(
    pg_data: list | dict,
    use_actual_card: bool = True,
) -> dict:
    """
    Convert PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) to Umbra-style plan for T3.

    pg_data: either the list from EXPLAIN (e.g. [{"Plan": ..., "Execution Time": ...}])
             or the raw plan object {"Plan": ..., "Execution Time": ...}.
    use_actual_card: if True, use Actual Rows for cardinality; else Plan Rows.

    Returns dict with keys: "plan", "ius", "analyzePlanPipelines".
    """
    if isinstance(pg_data, list) and pg_data:
        pg_data = pg_data[0]
    root_pg = pg_data.get("Plan", pg_data)
    next_id = [1]
    root_umbra = _convert_node(root_pg, next_id, use_actual_card)

    pipeline_by_id: dict[int, int] = {}
    _assign_pipelines(root_umbra, pipeline_by_id, [0], [1])

    times_by_id: dict[int, tuple[float, float]] = {}
    _fill_times_pg(root_pg, root_umbra, times_by_id)

    pipelines_list: list[dict] = []
    pid_to_ids: dict[int, list[int]] = {}
    for nid, pid in pipeline_by_id.items():
        pid_to_ids.setdefault(pid, []).append(nid)
    for pid in sorted(pid_to_ids.keys()):
        ids = pid_to_ids[pid]
        starts = [times_by_id.get(i, (0, 0))[0] for i in ids]
        stops = [times_by_id.get(i, (0, 0))[1] for i in ids]
        start = min(starts) if starts else 0
        stop = max(stops) if stops else 0
        pipelines_list.append({"operators": ids, "start": start, "stop": stop, "duration": max(0, stop - start)})

    return {
        "plan": root_umbra,
        "ius": [],
        "analyzePlanPipelines": pipelines_list,
    }


def load_pg_json(path: str | Path) -> dict:
    """Load PG EXPLAIN JSON file and return structure expected by pg_explain_to_umbra."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data
