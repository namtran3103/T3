"""
Load parsed_plans JSON (zero-shot style) and run Johannes pipeline: rewrite_children,
annotate_op_id, extract_pipeline_infos, QueryPlan, build_pipelines, BenchmarkedQuery.
No dependency on src.zeroshot or raw PG.
"""
import copy
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .jh_benchmarked_query import BenchmarkedQuery
from .jh_query_plan import CardType, QueryPlan


def _filter_columns_to_jh_expression(fc: dict) -> Optional[dict]:
    """Convert parsed_plans filter_columns (operator, children) to JH plan_parameters filter (operator, children)."""
    if not fc or not isinstance(fc, dict):
        return None
    op = (fc.get("operator") or "").strip().upper()
    children = fc.get("children", [])
    if op == "AND":
        inputs = []
        for c in children:
            sub = _filter_columns_to_jh_expression(c)
            if sub:
                inputs.append(sub)
        if not inputs:
            return None
        return {"operator": "and", "children": inputs}
    if op == "OR":
        inputs = []
        for c in children:
            sub = _filter_columns_to_jh_expression(c)
            if sub:
                inputs.append(sub)
        if not inputs:
            return None
        return {"operator": "or", "children": inputs}
    if op == "NOT" and children:
        sub = _filter_columns_to_jh_expression(children[0])
        if sub:
            return {"operator": "not", "children": [sub]}
        return None
    # Leaf: map to JH operator name
    if op in ("=", "EQ"):
        return {"operator": "="}
    if op in (">=", "GEQ"):
        return {"operator": ">="}
    if op in (">", "GT"):
        return {"operator": ">"}
    if op in ("<=", "LEQ"):
        return {"operator": "<="}
    if op in ("<", "LT"):
        return {"operator": "<"}
    if op in ("!=", "NEQ", "<>"):
        return {"operator": "!="}
    if op in ("LIKE",):
        return {"operator": "like"}
    if op in ("IN",):
        return {"operator": "in"}
    if op in ("BETWEEN",):
        return {"operator": "between"}
    if op in ("STARTSWITH",):
        return {"operator": "startswith"}
    if op in ("ISNOTNULL", "IS NOT NULL"):
        return {"operator": "IS NOT NULL"}
    if op in ("ISNULL", "IS NULL"):
        return {"operator": "IS NULL"}
    return {"operator": "="}


def _normalize_plan_node(node: dict, run_file_id: str, table_stats: dict) -> None:
    """Mutate node: add table_name for scans, filter from filter_columns; collect table stats."""
    if not node or "plan_parameters" not in node:
        return
    pp = node["plan_parameters"]
    op_name = pp.get("op_name", "")
    if op_name in ("Seq Scan", "Parallel Seq Scan"):
        tid = pp.get("table")
        if tid is not None:
            tname = f"t{tid}"
            pp["table_name"] = tname
            if tname not in table_stats:
                table_stats[tname] = max(1, float(pp.get("act_card", pp.get("est_card", 1))))
        else:
            pp["table_name"] = "unknown"
            table_stats["unknown"] = max(1, float(pp.get("act_card", pp.get("est_card", 1))))
    if "filter_columns" in pp and pp["filter_columns"]:
        f = _filter_columns_to_jh_expression(pp["filter_columns"])
        if f:
            pp["filter"] = f
    for ch in node.get("children", []):
        _normalize_plan_node(ch, run_file_id, table_stats)


def _check_plan_runtime_validity(plan: dict, parent_runtime: float) -> bool:
    """True if plan runtimes are consistent (child <= parent)."""
    pp = plan.get("plan_parameters", {})
    act = float(pp.get("act_time", 0))
    if act < 0 or act > parent_runtime * 1.01:
        return False
    for key in ("input", "left", "right"):
        if key in plan:
            if not _check_plan_runtime_validity(plan[key], act):
                return False
    return True


class UnsupportedOperatorException(Exception):
    pass


def annotate_op_id(parsed_plan: dict, id: int = -1) -> int:
    id = id + 1
    parsed_plan["plan_parameters"]["op_id"] = id + 1
    parsed_plan["plan_parameters"]["analyze_plan_id"] = id
    if "input" in parsed_plan:
        id = annotate_op_id(parsed_plan["input"], id)
    if "left" in parsed_plan:
        id = annotate_op_id(parsed_plan["left"], id)
        if parsed_plan["right"] is not None:
            id = annotate_op_id(parsed_plan["right"], id)
    return id


def add_table_stats_dict(db_statistics: dict) -> None:
    table_stats = db_statistics.get("table_stats", [])
    if isinstance(table_stats, dict):
        db_statistics["table_stats_dict"] = table_stats
        return
    table_stats_dict = {}
    for entry in table_stats:
        if isinstance(entry, dict) and "relname" in entry:
            table_stats_dict[entry["relname"]] = entry
        elif isinstance(entry, dict):
            relname = entry.get("relname", "unknown")
            table_stats_dict[relname] = entry
    if not table_stats_dict:
        for k, v in db_statistics.get("table_stats_dict", {}).items():
            table_stats_dict[k] = {"relname": k, "reltuples": v} if isinstance(v, (int, float)) else v
    db_statistics["table_stats_dict"] = table_stats_dict


def construct_pseudo_pipeline(op_ids: list, runtime: float) -> dict:
    return {"duration": max(0, runtime), "parallelism": None, "operators": op_ids}


def add_order_to_pipelines(pipelines: list) -> None:
    start_ts = 0
    for i in range(len(pipelines) - 1, -1, -1):
        p = pipelines[i]
        p["start"] = start_ts
        start_ts += p["duration"]
        p["stop"] = start_ts


def extract_pipeline_infos(parsed_plan: dict, pipelines: list, root: bool = True) -> Tuple[Optional[list], float]:
    operator = parsed_plan["plan_parameters"]["op_name"]
    analyze_plan_id = parsed_plan["plan_parameters"]["analyze_plan_id"]
    act_time = float(parsed_plan["plan_parameters"].get("act_time", 0))

    if root:
        pipeline_op_ids, child_pipelines_runtime = extract_pipeline_infos(parsed_plan, pipelines, root=False)
        total_plan_runtime = float(parsed_plan.get("plan_runtime_ms", act_time))
        pipelines.insert(
            0,
            construct_pseudo_pipeline(
                op_ids=pipeline_op_ids or [],
                runtime=total_plan_runtime - child_pipelines_runtime,
            ),
        )
        pipeline_runtimes = [float(p.get("duration") or 0) for p in pipelines]
        total_runtime_sum = sum(pipeline_runtimes)
        if total_runtime_sum >= 1e-9 and not np.isclose(total_runtime_sum, total_plan_runtime):
            scale = total_plan_runtime / total_runtime_sum
            for p in pipelines:
                p["duration"] = float(p.get("duration") or 0) * scale
        add_order_to_pipelines(pipelines)
        return None, total_plan_runtime

    if "input" in parsed_plan:
        child_stream, child_pipelines_runtime = extract_pipeline_infos(parsed_plan["input"], pipelines=pipelines, root=False)
        child_streams = [child_stream]
        child_pipelines_runtimes = [child_pipelines_runtime]
    elif "left" in parsed_plan:
        left, left_runtime = extract_pipeline_infos(parsed_plan["left"], pipelines=pipelines, root=False)
        child_streams = [left]
        child_pipelines_runtimes = [left_runtime]
        if operator not in ["Index Nested Loop"] and parsed_plan.get("right") is not None:
            right, right_runtime = extract_pipeline_infos(parsed_plan["right"], pipelines=pipelines, root=False)
            child_streams.append(right)
            child_pipelines_runtimes.append(right_runtime)
    else:
        child_streams = []
        child_pipelines_runtimes = [0]

    child_pipelines_runtimes = [max(0, x) for x in child_pipelines_runtimes]

    if operator in ["Sort", "Aggregate", "Simple Aggregate", "Finalize Aggregate"]:
        if len(child_streams) != 1:
            return [analyze_plan_id], act_time
        op_ids = [analyze_plan_id] + (child_streams[0] or [])
        pipelines.insert(
            0,
            construct_pseudo_pipeline(op_ids=op_ids, runtime=act_time - (child_pipelines_runtimes[0] or 0)),
        )
        return [analyze_plan_id], act_time

    if len(child_streams) == 2:
        if operator == "Hash Join":
            left_runtime = float(parsed_plan["plan_parameters"].get("left_runtime", 0)) - (child_pipelines_runtimes[0] or 0)
            left_runtime = max(0, left_runtime)
            hash_pipeline = [analyze_plan_id] + (child_streams[0] or [])
            pipelines.insert(0, construct_pseudo_pipeline(hash_pipeline, left_runtime))
            return [analyze_plan_id] + (child_streams[1] or []), left_runtime + (child_pipelines_runtimes[0] or 0) + (child_pipelines_runtimes[1] or 0)
        if operator == "Merge Join":
            left_runtime = float(parsed_plan["plan_parameters"].get("left_runtime", 0)) - (child_pipelines_runtimes[0] or 0)
            left_runtime = max(0, left_runtime)
            right_runtime = float(parsed_plan["plan_parameters"].get("right_runtime", 0)) - (child_pipelines_runtimes[1] or 0)
            right_runtime = max(0, right_runtime)
            if right_runtime == 0:
                right_runtime += 1e-5
            pipelines.insert(0, construct_pseudo_pipeline([analyze_plan_id] + (child_streams[0] or []), left_runtime))
            pipelines.insert(0, construct_pseudo_pipeline([analyze_plan_id] + (child_streams[1] or []), right_runtime))
            return [analyze_plan_id], left_runtime + right_runtime + (child_pipelines_runtimes[0] or 0) + (child_pipelines_runtimes[1] or 0)
        if operator == "Nested Loop":
            left_runtime = float(parsed_plan["plan_parameters"].get("left_runtime", 0)) - (child_pipelines_runtimes[0] or 0)
            left_runtime = max(0, left_runtime)
            pipelines.insert(0, construct_pseudo_pipeline([analyze_plan_id] + (child_streams[0] or []), left_runtime))
            return [analyze_plan_id] + (child_streams[1] or []), left_runtime + (child_pipelines_runtimes[0] or 0) + (child_pipelines_runtimes[1] or 0)
        raise UnsupportedOperatorException(f"Unsupported join: {operator}")

    if len(child_streams) == 0:
        return [analyze_plan_id], 0
    pipeline_op_ids = [analyze_plan_id] + (child_streams[0] or [])
    return pipeline_op_ids, child_pipelines_runtimes[0] or 0


def prune_ops(node: dict) -> dict:
    if node["plan_parameters"]["op_name"] == "Materialize":
        if node.get("children") and len(node["children"]) == 1:
            node = node["children"][0]
            node = prune_ops(node)
    return node


def rewrite_children(parsed_plan: dict) -> None:
    if "children" not in parsed_plan or not parsed_plan["children"]:
        return
    children = parsed_plan.pop("children")
    if len(children) == 2:
        op_name = parsed_plan["plan_parameters"]["op_name"]
        if op_name == "Hash Join":
            child_op_names = [c["plan_parameters"]["op_name"] for c in children]
            if "Hash" not in child_op_names:
                raise UnsupportedOperatorException(f"No Hash in children: {child_op_names}")
            if child_op_names[1] != "Hash":
                raise UnsupportedOperatorException(f"Expected Hash at index 1: {child_op_names}")
            hash_op = children[1]
            if hash_op.get("children") and len(hash_op["children"]) == 1:
                children[1] = hash_op["children"][0]
            parsed_plan["plan_parameters"]["left_runtime"] = hash_op["plan_parameters"].get("act_time", 0)
            left = children[1]
            right = children[0]
        elif op_name == "Index Nested Loop":
            child_op_names = [c["plan_parameters"]["op_name"] for c in children]
            if "Index Scan" not in child_op_names and "Index Only Scan" not in child_op_names:
                raise UnsupportedOperatorException(f"No Index Scan in children: {child_op_names}")
            idx = 1 if (children[1]["plan_parameters"]["op_name"] in ("Index Scan", "Index Only Scan")) else 0
            parsed_plan["plan_parameters"]["idx_scan"] = children[idx]["plan_parameters"]
            left = children[1 - idx]
            right = children[idx]
        elif op_name == "Merge Join":
            left = children[0]
            right = children[1]
        elif op_name == "Nested Loop":
            left = children[1]
            right = children[0]
        else:
            raise UnsupportedOperatorException(f"Unsupported binary op: {op_name}")

        if "left_runtime" not in parsed_plan["plan_parameters"]:
            parsed_plan["plan_parameters"]["left_runtime"] = left["plan_parameters"].get("act_time", 0)
        parsed_plan["plan_parameters"]["right_runtime"] = right["plan_parameters"].get("act_time", 0)
        left = prune_ops(left)
        right = prune_ops(right)
        parsed_plan["left"] = left
        parsed_plan["right"] = right
        rewrite_children(left)
        rewrite_children(right)
        return

    if len(children) == 1:
        op_name = parsed_plan["plan_parameters"]["op_name"]
        if op_name == "Finalize Aggregate":
            def find_non_gather(node):
                if node["plan_parameters"]["op_name"] in ("Gather", "Partial Aggregate"):
                    ch = node.get("children", [])
                    if len(ch) == 1:
                        return find_non_gather(ch[0])
                return node
            input_node = find_non_gather(children[0])
            parsed_plan["plan_parameters"]["op_name"] = "Aggregate"
        elif op_name == "Simple Aggregate":
            input_node = children[0]
            parsed_plan["plan_parameters"]["op_name"] = "Aggregate"
        else:
            input_node = children[0]
        parsed_plan["plan_parameters"]["input_runtime"] = input_node["plan_parameters"].get("act_time", 0)
        input_node = prune_ops(input_node)
        parsed_plan["input"] = input_node
        rewrite_children(input_node)


def load_parsed_plans_from_json(
    json_paths: List[Path],
    use_actual_card: bool = True,
    card_type: Optional[CardType] = None,
    verbose: bool = False,
) -> Tuple[List[BenchmarkedQuery], List[dict]]:
    """
    Load parsed_plans from JSON files and return (list of BenchmarkedQuery, per-file diagnostics).
    Each file: {"parsed_plans": [ { plan_parameters, children, ... }, ... ]}.
    If verbose=True, per-file and per-plan skip reasons and exception messages are stored in diagnostics.
    """
    card_type = card_type or (CardType.act if use_actual_card else CardType.pg)
    table_stats_global = {}
    all_queries = []
    diagnostics = []

    for jpath in json_paths:
        run_file_id = jpath.stem
        diag = {
            "path": str(jpath),
            "plans_total": 0,
            "added": 0,
            "skip_runtime": 0,
            "skip_exception": 0,
            "skip_act_time_le_zero": 0,
            "skip_runtime_validity": 0,
            "exceptions": [],
        }
        try:
            with open(jpath, "r") as f:
                data = json.load(f)
        except Exception as e:
            diag["file_error"] = str(e)
            diagnostics.append(diag)
            continue

        plans = data.get("parsed_plans", [])
        diag["plans_total"] = len(plans)
        db_statistics = {"table_stats": [], "table_stats_dict": {}}

        for idx, raw_plan in enumerate(plans):
            try:
                plan = copy.deepcopy(raw_plan)
                root_act_time = float(plan.get("plan_parameters", {}).get("act_time", 0))
                plan["plan_runtime_ms"] = root_act_time
                plan["sql"] = ""
                plan["run_file_id"] = run_file_id

                _normalize_plan_node(plan, run_file_id, table_stats_global)

                if root_act_time <= 0:
                    diag["skip_runtime"] += 1
                    diag["skip_act_time_le_zero"] += 1
                    if verbose:
                        diag["exceptions"].append((idx, "act_time_le_zero", f"root act_time={root_act_time}"))
                    continue
                if not _check_plan_runtime_validity(plan, root_act_time):
                    diag["skip_runtime"] += 1
                    diag["skip_runtime_validity"] += 1
                    if verbose:
                        diag["exceptions"].append((idx, "runtime_validity", "child runtime > parent or invalid"))
                    continue

                rewrite_children(plan)
                annotate_op_id(plan)
                pipelines = []
                extract_pipeline_infos(plan, pipelines)

                db_statistics["table_stats_dict"] = {
                    t: {"relname": t, "reltuples": v} for t, v in table_stats_global.items()
                }
                if not db_statistics["table_stats_dict"]:
                    db_statistics["table_stats_dict"] = {"unknown": {"relname": "unknown", "reltuples": 1}}

                qp = QueryPlan(plan, card_type, db_statistics)
                qp.build_pipelines(pipelines)
                if not qp.pipelines:
                    diag["skip_exception"] += 1
                    diag["exceptions"].append((idx, "no_pipelines", "all pipelines had missing op_ids"))
                    continue
                runtime_sec = root_act_time / 1000.0
                name = f"{run_file_id}_{idx}" if len(plans) > 1 else run_file_id
                bq = BenchmarkedQuery(
                    query_plan=qp,
                    total_runtimes=[runtime_sec],
                    name=name,
                    query_text="",
                    query_category=None,
                    source_path=str(jpath),
                    plan_index=idx,
                )
                all_queries.append(bq)
                diag["added"] += 1
            except UnsupportedOperatorException as e:
                diag["skip_exception"] += 1
                diag["exceptions"].append((idx, "UnsupportedOperatorException", str(e)))
            except Exception as e:
                diag["skip_exception"] += 1
                diag["exceptions"].append((idx, type(e).__name__, str(e)))

        diagnostics.append(diag)

    return all_queries, diagnostics


def collect_all_jsons(data_dir: Path) -> List[Path]:
    """Collect all .json files under data_dir (recursive)."""
    return list(Path(data_dir).rglob("*.json"))
