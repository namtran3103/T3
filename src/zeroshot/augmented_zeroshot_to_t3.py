"""
Map zero-shot DeepDB-augmented plan JSON (runs/deepdb_augmented) to T3 format.

Same as zeroshot_to_t3 but uses DeepDB cardinality estimates when present:
- For estimated cardinality: dd_est_card if present, else est_card.
- For scan input size: dd_est_children_card if present, else act_children_card / est_children_card.

Use this module when training or evaluating on runs/deepdb_augmented/ (parsed + DeepDB SPN estimates).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Reuse pipeline/timing logic from zeroshot_to_t3; only cardinality helpers differ.
from src.zeroshot.zeroshot_to_t3 import (
    MIN_IU_BYTES,
    _get_width,
    _get_start_stop_us,
    _make_placeholder,
    _is_pipeline_breaker,
    _assign_pipelines,
    _fill_times_zeroshot,
    load_zeroshot_json,
    get_minimal_database,
    collect_all_zeroshot_jsons,
)


def _get_card(zs_node: dict, use_actual: bool) -> float:
    """Cardinality: actual (act_card) or DeepDB estimate (dd_est_card) if present else est_card."""
    p = zs_node.get("plan_parameters", {})
    if use_actual and "act_card" in p:
        return max(0, float(p["act_card"]))
    # Use DeepDB estimate when available (augmented runs)
    if "dd_est_card" in p and p["dd_est_card"] is not None:
        return max(0, float(p["dd_est_card"]))
    return max(0, float(p.get("est_card", 1)))


def _get_children_card(zs_node: dict) -> float:
    """Children cardinality for scans: prefer dd_est_children_card (DeepDB), else act/est."""
    p = zs_node.get("plan_parameters", {})
    if "dd_est_children_card" in p and p["dd_est_children_card"] is not None:
        return max(1, float(p["dd_est_children_card"]))
    return max(1, float(p.get("act_children_card", p.get("est_children_card", 1))))


def _convert_node(zs_node: dict, next_id: list[int], use_actual_card: bool) -> dict:
    """Convert one zero-shot plan node to Umbra-style. Mutates next_id[0]."""
    if not zs_node or not zs_node.get("plan_parameters"):
        return _make_placeholder(next_id)
    nid = next_id[0]
    next_id[0] += 1
    p = zs_node["plan_parameters"]
    op_name = (p.get("op_name") or "").strip()
    card = _get_card(zs_node, use_actual_card)
    width = _get_width(zs_node)
    children = zs_node.get("children", [])

    out: dict[str, Any] = {
        "operator": "",
        "operatorId": nid,
        "analyzePlanId": nid,
        "cardinality": card,
        "analyzePlanCardinality": _get_card(zs_node, True),
        "producedIUs": [{"estimatedSize": int(width)}],
        "restrictions": [],
        "residuals": [],
    }
    out["pg"] = dict(p)

    # Scans: use DeepDB-aware children card for inputCardinality
    if op_name in ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan"):
        out["operator"] = "tablescan"
        out["tablename"] = "unknown"
        out["inputCardinality"] = int(_get_children_card(zs_node))
        if out["inputCardinality"] < 0:
            out["inputCardinality"] = 1
        fc = p.get("filter_columns")
        if isinstance(fc, dict) and fc.get("column") is not None:
            out["restrictions"].append({"expression": "compare", "estimatedSelectivity": 0.1})
        return out

    # Hash Join
    if op_name == "Hash Join":
        out["operator"] = "join"
        out["physicalOperator"] = "hashjoin"
        outer = children[0] if len(children) > 0 else None
        inner = children[1] if len(children) > 1 else None
        if inner and inner.get("plan_parameters", {}).get("op_name") == "Hash":
            inner = (inner.get("children") or [None])[0]
        out["left"] = _convert_node(outer, next_id, use_actual_card) if outer else _make_placeholder(next_id)
        out["right"] = _convert_node(inner, next_id, use_actual_card) if inner else _make_placeholder(next_id)
        return out

    # Merge Join
    if op_name == "Merge Join":
        out["operator"] = "join"
        out["physicalOperator"] = "hashjoin"
        out["left"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        out["right"] = _convert_node(children[1], next_id, use_actual_card) if len(children) > 1 else _make_placeholder(next_id)
        return out

    # Nested Loop
    if op_name == "Nested Loop":
        out["operator"] = "join"
        out["physicalOperator"] = "indexnljoin"
        out["left"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        out["right"] = _convert_node(children[1], next_id, use_actual_card) if len(children) > 1 else _make_placeholder(next_id)
        return out

    # Aggregate
    if op_name in ("Aggregate", "Partial Aggregate", "Finalize Aggregate"):
        out["operator"] = "groupby"
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Sort
    if op_name == "Sort":
        out["operator"] = "sort"
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Hash
    if op_name == "Hash":
        out["operator"] = "temp"
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Materialize
    if op_name == "Materialize":
        out["operator"] = "temp"
        out["pgMaterialize"] = True
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Pass-through
    if op_name in ("Gather", "Memoize", "Limit", "Append", "Subquery Scan", "Bitmap Heap Scan", "Bitmap Index Scan"):
        out["operator"] = "select"
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Default
    out["operator"] = "select"
    out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
    return out


def zeroshot_plan_to_t3(
    zs_plan: dict,
    use_actual_card: bool = True,
) -> dict:
    """
    Convert one DeepDB-augmented zero-shot plan to T3/Umbra format.
    Uses dd_est_card (and dd_est_children_card) when present for estimated cardinalities.
    """
    next_id = [1]
    root_umbra = _convert_node(zs_plan, next_id, use_actual_card)

    pipeline_by_id: dict[int, int] = {}
    _assign_pipelines(root_umbra, pipeline_by_id, [0], [1])

    times_by_id: dict[int, tuple[float, float]] = {}
    _fill_times_zeroshot(zs_plan, root_umbra, times_by_id)

    pid_to_ids: dict[int, list[int]] = {}
    for nid, pid in pipeline_by_id.items():
        pid_to_ids.setdefault(pid, []).append(nid)
    pipelines_list: list[dict] = []
    for pid in sorted(pid_to_ids.keys()):
        ids = pid_to_ids[pid]
        starts = [times_by_id.get(i, (0, 0))[0] for i in ids]
        stops = [times_by_id.get(i, (0, 0))[1] for i in ids]
        start = min(starts) if starts else 0
        stop = max(stops) if stops else 0
        pipelines_list.append({
            "operators": ids,
            "start": start,
            "stop": stop,
            "duration": max(0, stop - start) / 1e6,
        })

    ius_list = [{"iu": "default", "estimatedSize": MIN_IU_BYTES}]

    result: dict[str, Any] = {
        "plan": root_umbra,
        "ius": ius_list,
        "analyzePlanPipelines": pipelines_list,
    }
    if "plan_runtime" in zs_plan and zs_plan["plan_runtime"] is not None:
        result["plan_runtime_seconds"] = float(zs_plan["plan_runtime"]) / 1000.0
    return result


def convert_file_to_t3(
    json_path: str | Path,
    use_actual_card: bool = True,
) -> list[dict]:
    """Load a DeepDB-augmented JSON and convert each parsed plan to T3 format."""
    data = load_zeroshot_json(json_path)
    plans = data.get("parsed_plans", [])
    return [zeroshot_plan_to_t3(p, use_actual_card=use_actual_card) for p in plans]
