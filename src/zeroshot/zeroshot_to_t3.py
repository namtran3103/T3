"""
Map zero-shot parsed plan JSON (e.g. from zero-shot-data/runs/parsed_plans) to T3 format.

- Converts nested plan_parameters/children structure to Umbra-style plan (operator, left/right/input,
  analyzePlanId, cardinality, producedIUs, restrictions/residuals).
- Splits into pipelines using breakers: Hash, Materialize, Sort, Aggregate (and join build side).
- Generates feature vectors via T3 FeatureMapper and QueryPlan.

Does not modify any other project files. Uses a minimal in-memory Database for plans that do not
have a schema (tablename "unknown", inputCardinality set on scans).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from src.zeroshot.operator_stages_patch import apply_zeroshot_operator_stages_patch

apply_zeroshot_operator_stages_patch()

# Default IU size when width not available (bytes).
MIN_IU_BYTES = 8


def _get_card(zs_node: dict, use_actual: bool) -> float:
    """Cardinality from zero-shot plan_parameters."""
    p = zs_node.get("plan_parameters", {})
    if use_actual and "act_card" in p:
        return max(0, float(p["act_card"]))
    return max(0, float(p.get("est_card", 1)))


def _get_width(zs_node: dict) -> float:
    """Tuple width in bytes (est_width is in bits or bytes; treat as bytes if small, else bits/8)."""
    p = zs_node.get("plan_parameters", {})
    w = float(p.get("est_width", 8))
    if w > 0 and w < 2000:
        return max(MIN_IU_BYTES, w)
    return max(MIN_IU_BYTES, w / 8.0)


def _get_start_stop_us(zs_node: dict) -> tuple[float, float]:
    """Start and total time in microseconds (zero-shot uses ms)."""
    p = zs_node.get("plan_parameters", {})
    start_ms = float(p.get("act_startup_cost", 0))
    total_ms = float(p.get("act_time", 0))
    return start_ms * 1000, total_ms * 1000


def _filter_operator_to_expression(operator: str) -> tuple[str, Optional[str]]:
    """Map zero-shot filter operator to T3 expression type and optional direction."""
    if operator == "EQ":
        return "compare", "="
    if operator in ("GEQ", "GT"):
        return "compare", ">=" if operator == "GEQ" else ">"
    if operator in ("LEQ", "LT"):
        return "compare", "<=" if operator == "LEQ" else "<"
    if operator == "NEQ":
        return "compare", "<>"
    if operator == "LIKE":
        return "like", None
    if operator == "IN":
        return "in", None
    if operator == "BETWEEN":
        return "between", None
    if operator == "STARTSWITH":
        return "startswith", None
    if operator == "ISNOTNULL":
        return "isnotnull", None
    return "compare", "="


def _convert_filter_columns_to_tree(
    filter_cols: dict, overall_selectivity: Optional[float] = None
) -> Optional[dict]:
    """
    Convert filter_columns tree (zero-shot: operator, children) to query_plan tree format
    (expression, input). Does not flatten; returns a single nested dict.
    When overall_selectivity is provided (e.g. from enrichment), set it only on the root
    so the core can distribute it via _featurize_expression. Otherwise the core uses defaults.
    """
    if not isinstance(filter_cols, dict):
        return None

    operator = (filter_cols.get("operator") or "").strip().upper()
    children = filter_cols.get("children", [])

    # AND / OR: recursive tree
    if operator == "AND":
        if not children:
            return None
        input_list = []
        for child in children:
            sub = _convert_filter_columns_to_tree(child, None)
            if sub is not None:
                input_list.append(sub)
        if not input_list:
            return None
        node: dict = {"expression": "and", "input": input_list}
        if overall_selectivity is not None and 0 < overall_selectivity <= 1.0:
            node["estimatedSelectivity"] = overall_selectivity
        return node

    if operator == "OR":
        if not children:
            return None
        input_list = []
        for child in children:
            sub = _convert_filter_columns_to_tree(child, None)
            if sub is not None:
                input_list.append(sub)
        if not input_list:
            return None
        node = {"expression": "or", "input": input_list}
        if overall_selectivity is not None and 0 < overall_selectivity <= 1.0:
            node["estimatedSelectivity"] = overall_selectivity
        return node

    # NOT: single child
    if operator == "NOT":
        if not children:
            return None
        sub = _convert_filter_columns_to_tree(children[0], None)
        if sub is None:
            return None
        node = {"expression": "not", "input": sub}
        if overall_selectivity is not None and 0 < overall_selectivity <= 1.0:
            node["estimatedSelectivity"] = overall_selectivity
        return node

    # Leaf: compare, like, in, between, etc.
    expr_type, direction = _filter_operator_to_expression(operator)
    node = {"expression": expr_type}
    if direction is not None:
        node["direction"] = direction
    if overall_selectivity is not None and 0 < overall_selectivity <= 1.0:
        node["estimatedSelectivity"] = overall_selectivity
    return node


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

    # Scans
    if op_name in ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan"):
        out["operator"] = "tablescan"
        out["tablename"] = "unknown"
        # Always use 1 for scan input cardinality (historical zeroshot behaviour; filter method is kept).
        out["inputCardinality"] = 1
        
        # Convert filter_columns to a single tree restriction. Set overall_selectivity at root
        # only when we have it from enrichment (raw data); otherwise the core uses defaults.
        fc = p.get("filter_columns")
        overall_selectivity = p.get("overall_selectivity")
        if isinstance(fc, dict):
            tree = _convert_filter_columns_to_tree(fc, overall_selectivity)
            if tree is not None:
                out["restrictions"].append(tree)
        elif fc is not None:
            # Legacy: simple filter_columns (e.g. just column name)
            node = {"expression": "compare"}
            if overall_selectivity is not None and 0 < overall_selectivity <= 1.0:
                node["estimatedSelectivity"] = overall_selectivity
            node["direction"] = "="
            out["restrictions"].append(node)

        return out

    # Hash Join: map so left=build (inner), right=probe (outer) to match Umbra operator_stages
    if op_name == "Hash Join":
        out["operator"] = "join"
        out["physicalOperator"] = "hashjoin"
        outer = children[0] if len(children) > 0 else None
        inner = children[1] if len(children) > 1 else None
        if inner and inner.get("plan_parameters", {}).get("op_name") == "Hash":
            inner = (inner.get("children") or [None])[0]
        out["left"] = _convert_node(inner, next_id, use_actual_card) if inner else _make_placeholder(next_id)
        out["right"] = _convert_node(outer, next_id, use_actual_card) if outer else _make_placeholder(next_id)
        return out

    # Merge Join (treat as hash join for pipeline structure): left=build (inner), right=probe (outer)
    if op_name == "Merge Join":
        out["operator"] = "join"
        out["physicalOperator"] = "hashjoin"
        outer = children[0] if len(children) > 0 else None
        inner = children[1] if len(children) > 1 else None
        out["left"] = _convert_node(inner, next_id, use_actual_card) if inner else _make_placeholder(next_id)
        out["right"] = _convert_node(outer, next_id, use_actual_card) if outer else _make_placeholder(next_id)
        return out

    # Nested Loop: map to indexnljoin (left=probe/outer, right=build/inner) to match Umbra and pg_to_umbra.
    if op_name == "Nested Loop":
        out["operator"] = "join"
        out["physicalOperator"] = "indexnljoin"
        out["left"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        out["right"] = _convert_node(children[1], next_id, use_actual_card) if len(children) > 1 else _make_placeholder(next_id)
        return out

    # Aggregate (all variants)
    if op_name in ("Aggregate", "Partial Aggregate", "Finalize Aggregate"):
        out["operator"] = "groupby"
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Sort
    if op_name == "Sort":
        out["operator"] = "sort"
        out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
        return out

    # Hash (build side of hash join)
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

    # Default: unary
    out["operator"] = "select"
    out["input"] = _convert_node(children[0], next_id, use_actual_card) if len(children) > 0 else _make_placeholder(next_id)
    return out


def _make_placeholder(next_id: list[int]) -> dict:
    """Minimal placeholder node when child is missing."""
    nid = next_id[0]
    next_id[0] += 1
    return {
        "operator": "tablescan",
        "operatorId": nid,
        "analyzePlanId": nid,
        "cardinality": 0,
        "analyzePlanCardinality": 0,
        "tablename": "unknown",
        "inputCardinality": 1,
        "producedIUs": [{"estimatedSize": MIN_IU_BYTES}],
        "restrictions": [],
        "residuals": [],
    }


def _is_pipeline_breaker(node: dict) -> bool:
    op = node.get("operator", "")
    return op in ("sort", "groupby") or (op == "temp" and node.get("pgMaterialize"))


def _assign_pipelines_children(
    node: dict,
    pipeline_by_id: dict[int, int],
    current_pipeline: list[int],
    next_pipeline_id: list[int],
) -> None:
    """Assign pipeline IDs to the descendants of node only (not node itself)."""
    for key in ("left", "right", "input"):
        if key in node and isinstance(node[key], dict):
            _assign_pipelines(node[key], pipeline_by_id, current_pipeline, next_pipeline_id)


def _assign_pipelines(
    node: dict,
    pipeline_by_id: dict[int, int],
    current_pipeline: list[int],
    next_pipeline_id: list[int],
) -> int:
    nid = node.get("analyzePlanId")
    if nid is None:
        return current_pipeline[0]
    op = node.get("operator", "")
    phys = node.get("physicalOperator", "")

    if op == "join" and phys in ("hashjoin", "indexnljoin"):
        pipeline_by_id[nid] = current_pipeline[0]
        left_node = node["left"]
        left_nid = left_node.get("analyzePlanId") if isinstance(left_node, dict) else None
        if left_nid is not None and _is_pipeline_breaker(left_node):
            # Keep direct left child in join's pipeline so operator_stages sees it as previous op.
            pipeline_by_id[left_nid] = current_pipeline[0]
            next_pipeline_id[0] += 1
            _assign_pipelines_children(left_node, pipeline_by_id, [next_pipeline_id[0]], next_pipeline_id)
            next_pipeline_id[0] += 1
        else:
            _assign_pipelines(node["left"], pipeline_by_id, current_pipeline, next_pipeline_id)
            next_pipeline_id[0] += 1
        _assign_pipelines(node["right"], pipeline_by_id, [next_pipeline_id[0]], next_pipeline_id)
        return current_pipeline[0]

    if _is_pipeline_breaker(node):
        if "input" in node and isinstance(node["input"], dict):
            _assign_pipelines(node["input"], pipeline_by_id, current_pipeline, next_pipeline_id)
        next_pipeline_id[0] += 1
        pipeline_by_id[nid] = next_pipeline_id[0]
        return next_pipeline_id[0]

    if "input" in node and isinstance(node["input"], dict):
        child_pid = _assign_pipelines(node["input"], pipeline_by_id, current_pipeline, next_pipeline_id)
        pipeline_by_id[nid] = child_pid
        return child_pid

    pipeline_by_id[nid] = current_pipeline[0]
    for key in ("left", "right", "input"):
        if key in node and isinstance(node[key], dict):
            _assign_pipelines(node[key], pipeline_by_id, current_pipeline, next_pipeline_id)
    return current_pipeline[0]


def _fill_times_zeroshot(zs_node: dict, umbra_node: dict, times_by_id: dict[int, tuple[float, float]]) -> None:
    """Fill (start_us, stop_us) for each Umbra node from zero-shot node."""
    nid = umbra_node.get("analyzePlanId")
    if nid is not None and zs_node.get("plan_parameters"):
        start_us, stop_us = _get_start_stop_us(zs_node)
        times_by_id[nid] = (start_us, stop_us)
    children = zs_node.get("children", [])
    umbra_children = []
    if "left" in umbra_node:
        umbra_children.append(umbra_node["left"])
    if "right" in umbra_node:
        umbra_children.append(umbra_node["right"])
    if "input" in umbra_node:
        umbra_children.append(umbra_node["input"])
    # Hash Join: right may be under Hash in zero-shot
    if (
        umbra_node.get("physicalOperator") == "hashjoin"
        and len(children) > 1
        and children[1].get("plan_parameters", {}).get("op_name") == "Hash"
    ):
        inner_zs = (children[1].get("children") or [None])[0]
        if inner_zs and "right" in umbra_node:
            _fill_times_zeroshot(inner_zs, umbra_node["right"], times_by_id)
        if len(children) > 0:
            _fill_times_zeroshot(children[0], umbra_node["left"], times_by_id)
        return
    for i, uc in enumerate(umbra_children):
        if isinstance(uc, dict) and i < len(children) and children[i]:
            _fill_times_zeroshot(children[i], uc, times_by_id)


def zeroshot_plan_to_t3(
    zs_plan: dict,
    use_actual_card: bool = True,
) -> dict:
    """
    Convert one zero-shot parsed plan (single element from parsed_plans array) to T3/Umbra format.

    zs_plan: dict with keys plan_parameters, children, plan_runtime (optional).
    Returns dict with keys: plan, ius, analyzePlanPipelines, plan_runtime_seconds (optional).
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
        # zero-shot plan_runtime is in milliseconds
        result["plan_runtime_seconds"] = float(zs_plan["plan_runtime"]) / 1000.0
    return result


def load_zeroshot_json(path: str | Path) -> dict:
    """Load zero-shot JSON file (with parsed_plans array)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_minimal_database():
    """Return a minimal Database for zero-shot plans (no schema files)."""
    from src.database import Database
    from src.schemata import Schema, Table

    table = Table("unknown", {}, 1_000_000)
    schema = Schema(tables={"unknown": table}, join_columns={}, name="zeroshot")
    return Database(schema, None)


def convert_file_to_t3(
    json_path: str | Path,
    use_actual_card: bool = True,
) -> list[dict]:
    """
    Load a zero-shot JSON file and convert each parsed plan to T3 format.

    Returns list of T3 plan dicts (plan, ius, analyzePlanPipelines, plan_runtime_seconds).
    """
    data = load_zeroshot_json(json_path)
    plans = data.get("parsed_plans", [])
    return [zeroshot_plan_to_t3(p, use_actual_card=use_actual_card) for p in plans]


def generate_feature_vectors(t3_plan: dict):
    """
    Build T3 QueryPlan from converted plan dict and return feature vectors (per-pipeline matrix).

    Uses minimal database. Returns (feature_matrix, query_plan) or (None, None) on failure.
    """
    from src.features import FeatureMapper
    from src.query_plan import QueryPlan

    db = get_minimal_database()
    try:
        # QueryPlan expects dict with "plan" and "ius"; build_pipelines expects "analyzePlanPipelines"
        plan = QueryPlan(t3_plan, db, predicted_cardinalities=False)
        plan.build_pipelines(t3_plan["analyzePlanPipelines"])
        mapper = FeatureMapper()
        feature_matrix = mapper.get_pipeline_estimation_matrix(plan)
        return feature_matrix, plan
    except Exception:
        return None, None


def collect_all_zeroshot_jsons(root_dir: str | Path) -> list[Path]:
    """Collect all .json files under root_dir (e.g. parsed_plans directory)."""
    root = Path(root_dir)
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.json"))
