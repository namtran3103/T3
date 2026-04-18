"""
Postgres/zeroshot-native feature set for parsed_plans.

Builds feature vectors purely from plan_parameters (pg payload) attached to each node
in the T3-converted plan. Used by zeroshot training and inference instead of the
Umbra FeatureMapper when plan_dict is available.

If est_cards are used, vector still use act_cards naming but the values are the est_cards.

Observed execution timings (act_time, act_startup_cost, pipeline duration) are not
included as features; ground-truth runtimes are still used only as training labels.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.util import AutoNumber


# PG operator name groups for aggregate PgFeature (must match zeroshot_to_t3 op_name values)
# Extended to include all operators found in zero-shot-data/runs/parsed_plans
PG_OP_SCAN = (
    "Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan",
    "Bitmap Heap Scan", "Bitmap Index Scan", "Parallel Bitmap Heap Scan",
    "Parallel Index Scan", "Parallel Index Only Scan",
)
PG_OP_JOIN = ("Hash Join", "Merge Join", "Nested Loop")
PG_OP_SORT = ("Sort",)
PG_OP_AGG = ("Aggregate", "Partial Aggregate", "Finalize Aggregate")
PG_OP_TEMP = ("Hash", "Materialize")
PG_OP_SELECT = ("Gather", "Gather Merge")  # pass-through / parallelism

# All PG operators from parsed_plans (exhaustive list for operator-level features)
PG_OPERATORS = (
    "Aggregate", "Bitmap Heap Scan", "Bitmap Index Scan", "Finalize Aggregate",
    "Gather", "Gather Merge", "Hash", "Hash Join", "Index Only Scan", "Index Scan",
    "Materialize", "Merge Join", "Nested Loop", "Parallel Bitmap Heap Scan",
    "Parallel Index Only Scan", "Parallel Index Scan", "Parallel Seq Scan",
    "Partial Aggregate", "Seq Scan", "Sort",
)


class PgOpFeature(AutoNumber):
    """Basic features per PG operator (PG-native, no Umbra mapping)."""
    in_card = ()
    in_size = ()
    out_card = ()
    out_size = ()
    in_percentage = ()
    out_percentage = ()
    right_percentage = ()
    right_card = ()
    like_percentage = ()
    compare_percentage = ()
    in_expression_percentage = ()
    or_exp_percentage = ()
    empty_output = ()


class PgFeatureDim(AutoNumber):
    """Feature dimensions for PG operators."""
    scan = ()
    sink = ()
    input = ()
    out = ()
    right = ()
    right_card = ()
    input_card = ()
    expressions = ()
    empty_output = ()


def _pg_op_feature_dim_to_features(dim: PgFeatureDim) -> list[PgOpFeature]:
    """Map dimension to list of PgOpFeature."""
    if dim == PgFeatureDim.scan:
        return [PgOpFeature.in_card, PgOpFeature.in_size]
    if dim == PgFeatureDim.sink:
        return [PgOpFeature.out_card, PgOpFeature.out_size]
    if dim == PgFeatureDim.out:
        return [PgOpFeature.out_percentage]
    if dim == PgFeatureDim.input:
        return [PgOpFeature.in_percentage]
    if dim == PgFeatureDim.right:
        return [PgOpFeature.right_percentage]
    if dim == PgFeatureDim.right_card:
        return [PgOpFeature.right_card]
    if dim == PgFeatureDim.input_card:
        return [PgOpFeature.in_card]
    if dim == PgFeatureDim.expressions:
        return [
            PgOpFeature.like_percentage,
            PgOpFeature.compare_percentage,
            PgOpFeature.in_expression_percentage,
            PgOpFeature.or_exp_percentage,
        ]
    if dim == PgFeatureDim.empty_output:
        return [PgOpFeature.empty_output]
    return []


# PG-native operator feature mapping: op_name -> list of feature dimensions
# No stages: each PG operator is a distinct node (e.g. Hash is separate from Hash Join)
PG_OP_FEATURES: dict[str, list[PgFeatureDim]] = {
    # Scans (read tuples, may have filter_columns)
    "Seq Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Parallel Seq Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Index Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Index Only Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Bitmap Heap Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Bitmap Index Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Parallel Bitmap Heap Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Parallel Index Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    "Parallel Index Only Scan": [PgFeatureDim.scan, PgFeatureDim.out, PgFeatureDim.expressions, PgFeatureDim.empty_output],
    # Hash (build side of hash join - separate node in PG)
    "Hash": [PgFeatureDim.sink, PgFeatureDim.input],
    # Materialize (build side)
    "Materialize": [PgFeatureDim.sink, PgFeatureDim.input],
    # Joins
    "Hash Join": [PgFeatureDim.input_card, PgFeatureDim.right, PgFeatureDim.out],
    "Merge Join": [PgFeatureDim.input_card, PgFeatureDim.right, PgFeatureDim.out],
    "Nested Loop": [PgFeatureDim.input, PgFeatureDim.right_card, PgFeatureDim.out],
    # Sort
    "Sort": [PgFeatureDim.sink, PgFeatureDim.input, PgFeatureDim.out],
    # Aggregates
    "Aggregate": [PgFeatureDim.sink, PgFeatureDim.input, PgFeatureDim.out],
    "Partial Aggregate": [PgFeatureDim.sink, PgFeatureDim.input, PgFeatureDim.out],
    "Finalize Aggregate": [PgFeatureDim.sink, PgFeatureDim.input, PgFeatureDim.out],
    # Pass-through / parallelism
    "Gather": [PgFeatureDim.input, PgFeatureDim.out],
    "Gather Merge": [PgFeatureDim.input, PgFeatureDim.out],
}

# Fallback for unknown operators (e.g. Memoize, Limit if they appear in future data)
_PG_OP_FALLBACK = [PgFeatureDim.input, PgFeatureDim.out]


def _get_pipeline_ops_in_execution_order(
    pipeline_op_ids: list[int],
    id_to_node: dict[int, dict],
    root_node: dict,
) -> list[tuple[int, dict]]:
    """Return (nid, node) list in execution order (post-order: children before parent)."""
    pipeline_set = set(pipeline_op_ids)
    result: list[tuple[int, dict]] = []

    def _postorder(node: dict) -> None:
        for key in ("left", "right", "input"):
            child = node.get(key)
            if isinstance(child, dict):
                _postorder(child)
        nid = node.get("analyzePlanId")
        if nid is not None and nid in pipeline_set:
            result.append((nid, node))

    _postorder(root_node)
    return result


def _get_child_act_card(node: dict, key: str, id_to_node: dict[int, dict]) -> float:
    """Get act_card from child at key (left/right/input)."""
    child = node.get(key)
    if not isinstance(child, dict):
        return 0.0
    nid = child.get("analyzePlanId")
    if nid is not None:
        child = id_to_node.get(nid, child)
    pg = (child or {}).get("pg") or {}
    return max(0, float(pg.get("act_card", pg.get("est_card", 0))))


def _pg_op_name_to_feature_key(op_name: str) -> str:
    """Normalize op_name for feature key (e.g. 'Hash Join' -> 'Hash_Join')."""
    return op_name.replace(" ", "_")


def _pg_enumerate_operator_features() -> list[tuple[str, str]]:
    """Enumerate (op_key, feature_name) for fixed vector layout. op_key = op_name with spaces replaced."""
    result: list[tuple[str, str]] = []
    for op_name in PG_OPERATORS:
        op_key = _pg_op_name_to_feature_key(op_name)
        dims = PG_OP_FEATURES.get(op_name, _PG_OP_FALLBACK)
        result.append((op_key, "const"))
        for dim in dims:
            for feat in _pg_op_feature_dim_to_features(dim):
                result.append((op_key, feat.name))
    # Other: fallback for operators not in PG_OPERATORS (e.g. Memoize, Limit from other data)
    result.append(("Other", "const"))
    for feat in _pg_op_feature_dim_to_features(PgFeatureDim.input) + _pg_op_feature_dim_to_features(PgFeatureDim.out):
        result.append(("Other", feat.name))
    return result


def _extract_operator_features(
    pipeline_op_ids: list[int],
    id_to_node: dict[int, dict],
    root_node: dict,
) -> np.ndarray:
    """Build operator-level feature vector for one pipeline (sum over ops). No stages."""
    ordered = _get_pipeline_ops_in_execution_order(pipeline_op_ids, id_to_node, root_node)
    pipeline_scan_card = 0.0
    for nid in pipeline_op_ids:
        node = id_to_node.get(nid)
        if node is None:
            continue
        pg = node.get("pg") or {}
        op_name = (pg.get("op_name") or "").strip()
        if op_name in PG_OP_SCAN:
            pipeline_scan_card += max(0, float(pg.get("act_card", pg.get("est_card", 0))))
    if pipeline_scan_card <= 0:
        pipeline_scan_card = 1.0  # avoid div-by-zero

    feature_spec = _pg_enumerate_operator_features()
    vec = np.zeros(len(feature_spec), dtype=float)

    accum: dict[str, dict[str, float]] = {}

    for nid, node in ordered:
        pg = node.get("pg") or {}
        op_name = (pg.get("op_name") or "").strip()
        dims = PG_OP_FEATURES.get(op_name, _PG_OP_FALLBACK) if op_name in PG_OPERATORS else _PG_OP_FALLBACK

        act_card = max(0, float(pg.get("act_card", pg.get("est_card", 0))))
        est_width = max(0, float(pg.get("est_width", 8)))
        left_card = _get_child_act_card(node, "left", id_to_node)
        right_card = _get_child_act_card(node, "right", id_to_node)
        input_card = _get_child_act_card(node, "input", id_to_node)

        # Hash Join: left=build, right=probe. input_card=probe stream, right_card=build size
        if op_name in ("Hash Join", "Merge Join"):
            in_card = right_card  # probe input
            probe_right_card = left_card  # build size
        else:
            in_card = input_card if input_card > 0 else left_card
            probe_right_card = right_card
        if in_card <= 0 and op_name in PG_OP_SCAN:
            in_card = act_card  # scan input = self for leaf scans

        in_pct = in_card / pipeline_scan_card if pipeline_scan_card > 0 else 0
        out_pct = act_card / pipeline_scan_card if pipeline_scan_card > 0 else 0
        right_pct = right_card / pipeline_scan_card if pipeline_scan_card > 0 else 0

        counts = _count_filter_columns(pg.get("filter_columns")) if pg.get("filter_columns") else {}
        total_expr = sum(counts.values()) or 1
        like_pct = counts.get("like", 0) / total_expr
        compare_pct = counts.get("compare", 0) / total_expr
        in_expr_pct = counts.get("in", 0) / total_expr
        or_pct = counts.get("or", 0) / total_expr

        op_key = _pg_op_name_to_feature_key(op_name) if op_name in PG_OPERATORS else "Other"
        if op_key not in accum:
            accum[op_key] = {
                "const": 0,
                "in_card": 0, "in_size": 0, "out_card": 0, "out_size": 0,
                "in_percentage": 0, "out_percentage": 0, "right_percentage": 0, "right_card": 0,
                "like_percentage": 0, "compare_percentage": 0, "in_expression_percentage": 0,
                "or_exp_percentage": 0,
                "empty_output": 0,
            }
        acc = accum[op_key]
        acc["const"] += 1
        for dim in dims:
            if dim == PgFeatureDim.scan:
                acc["in_card"] += in_card
                acc["in_size"] += est_width
            elif dim == PgFeatureDim.sink:
                acc["out_card"] += act_card
                acc["out_size"] += est_width
            elif dim == PgFeatureDim.input:
                acc["in_percentage"] += in_pct
            elif dim == PgFeatureDim.out:
                acc["out_percentage"] += out_pct
            elif dim == PgFeatureDim.right:
                acc["right_percentage"] += right_pct
            elif dim == PgFeatureDim.right_card:
                acc["right_card"] += probe_right_card
            elif dim == PgFeatureDim.input_card:
                acc["in_card"] += in_card
            elif dim == PgFeatureDim.expressions:
                acc["like_percentage"] += like_pct
                acc["compare_percentage"] += compare_pct
                acc["in_expression_percentage"] += in_expr_pct
                acc["or_exp_percentage"] += or_pct
            elif dim == PgFeatureDim.empty_output:
                acc["empty_output"] += 1 if act_card == 0 else 0

    for i, (op_key, feat_name) in enumerate(feature_spec):
        acc = accum.get(op_key, {})
        if feat_name == "const":
            vec[i] = acc.get("const", 0)
        else:
            vec[i] = acc.get(feat_name, 0)
    return vec


class PgFeature(AutoNumber):
    """All features derivable from parsed_plans plan_parameters, aggregated per pipeline.

    Does not include observed operator or pipeline timings (no act_time / startup / duration in X)
    so runtime prediction does not use target leakage from EXPLAIN ANALYZE times as inputs.
    """

    # Cardinality
    pg_card_sum = ()
    pg_card_max = ()

    # Planner cost (PostgreSQL est_cost / est_startup_cost)
    pg_est_cost_sum = ()
    pg_est_cost_max = ()
    pg_est_startup_sum = ()

    # Parallelism (planner: workers planned per node)
    pg_workers_planned_sum = ()

    # Width
    pg_est_width_avg = ()

    # Operator counts
    pg_num_scan = ()
    pg_num_join = ()
    pg_num_sort = ()
    pg_num_agg = ()
    pg_num_temp = ()
    pg_num_select = ()

    # Scan-specific (only scan ops in pipeline; actual only, estimate fallback)
    pg_scan_act_card_sum = ()
    pg_scan_has_filter = ()

    # Filter structure (from filter_columns tree on scans)
    pg_filter_and_count = ()
    pg_filter_or_count = ()
    pg_filter_compare_count = ()
    pg_filter_like_count = ()
    pg_filter_in_count = ()

    # Sum of parser `table` ids on scans in the pipeline (plan_parameters)
    pg_table_id_sum = ()

    # Pipeline-level (structure; no observed pipeline duration in features)
    pg_pipeline_num_ops = ()
    pg_pipeline_root_act_card = ()


# Fixed order for vector index (must match PgFeature enum definition order)
def _pg_feature_list():
    return list(PgFeature)


def _collect_nodes_by_id(node: dict, out: dict[int, dict]) -> None:
    """Recursively collect each node by analyzePlanId. Mutates out."""
    nid = node.get("analyzePlanId")
    if nid is not None:
        out[nid] = node
    for key in ("left", "right", "input"):
        if key in node and isinstance(node.get(key), dict):
            _collect_nodes_by_id(node[key], out)


def _count_filter_columns(fc: Any) -> dict[str, int]:
    """Count AND, OR, compare, like, in (between/startswith dropped: not in zeroshot parsed_plans)."""
    counts = {"and": 0, "or": 0, "compare": 0, "like": 0, "in": 0}
    if not isinstance(fc, dict):
        return counts
    op = (fc.get("operator") or "").strip().upper()
    children = fc.get("children", [])
    if op == "AND":
        counts["and"] += 1
        for c in children:
            for k, v in _count_filter_columns(c).items():
                counts[k] += v
    elif op == "OR":
        counts["or"] += 1
        for c in children:
            for k, v in _count_filter_columns(c).items():
                counts[k] += v
    elif op in ("NOT",) and children:
        for k, v in _count_filter_columns(children[0]).items():
            counts[k] += v
    elif op in ("=", "EQ", ">=", "GEQ", ">", "GT", "<=", "LEQ", "<", "LT", "!=", "NEQ", "<>"):
        counts["compare"] += 1
    elif op in ("LIKE", "NOT LIKE"):
        counts["like"] += 1
    elif op == "IN":
        counts["in"] += 1
    elif op in ("ISNOTNULL", "IS NULL", "IS NOT NULL"):
        counts["compare"] += 1
    return counts


def _extract_pipeline_pg_features(
    pipeline_op_ids: list[int],
    id_to_node: dict[int, dict],
    root_act_card: float,
) -> np.ndarray:
    """Build one fixed-length feature vector for a single pipeline."""
    n_features = len(PgFeature)
    vec = np.zeros(n_features, dtype=float)

    act_cards = []
    est_costs = []
    est_startups = []
    widths = []
    num_scan = 0
    num_join = 0
    num_sort = 0
    num_agg = 0
    num_temp = 0
    num_select = 0
    scan_act_sum = 0.0
    scan_has_filter = 0
    filter_and = 0
    filter_or = 0
    filter_compare = 0
    filter_like = 0
    filter_in = 0
    table_id_sum = 0
    workers_planned_sum = 0.0

    for nid in pipeline_op_ids:
        node = id_to_node.get(nid)
        if node is None:
            continue
        pg = node.get("pg") or {}
        op_name = (pg.get("op_name") or "").strip()

        act_card = max(0, float(pg.get("act_card", pg.get("est_card", 0))))
        width = max(0, float(pg.get("est_width", 8)))
        try:
            ec = float(pg.get("est_cost", 0) or 0)
        except (TypeError, ValueError):
            ec = 0.0
        est_costs.append(max(0.0, ec))
        try:
            esu = float(pg.get("est_startup_cost", 0) or 0)
        except (TypeError, ValueError):
            esu = 0.0
        est_startups.append(max(0.0, esu))

        wp = pg.get("workers_planned")
        if wp is not None:
            try:
                workers_planned_sum += max(0.0, float(wp))
            except (TypeError, ValueError):
                pass

        act_cards.append(act_card)
        widths.append(width)

        if op_name in PG_OP_SCAN:
            num_scan += 1
            scan_act_sum += act_card
            fc = pg.get("filter_columns")
            if fc is not None and (isinstance(fc, dict) or (isinstance(fc, list) and len(fc) > 0)):
                scan_has_filter = 1
            counts = _count_filter_columns(fc) if fc else {}
            filter_and += counts.get("and", 0)
            filter_or += counts.get("or", 0)
            filter_compare += counts.get("compare", 0)
            filter_like += counts.get("like", 0)
            filter_in += counts.get("in", 0)
            tid = pg.get("table")
            if tid is not None:
                try:
                    table_id_sum += int(tid)
                except (TypeError, ValueError):
                    pass
        elif op_name in PG_OP_JOIN:
            num_join += 1
        elif op_name in PG_OP_SORT:
            num_sort += 1
        elif op_name in PG_OP_AGG:
            num_agg += 1
        elif op_name in PG_OP_TEMP:
            num_temp += 1
        elif op_name in PG_OP_SELECT:
            num_select += 1
        else:
            # default: count as select (pass-through)
            num_select += 1

    # Fill vector in PgFeature enum order
    values = {
        PgFeature.pg_card_sum: sum(act_cards),
        PgFeature.pg_card_max: max(act_cards) if act_cards else 0,
        PgFeature.pg_est_cost_sum: sum(est_costs),
        PgFeature.pg_est_cost_max: max(est_costs) if est_costs else 0,
        PgFeature.pg_est_startup_sum: sum(est_startups),
        PgFeature.pg_workers_planned_sum: workers_planned_sum,
        PgFeature.pg_est_width_avg: float(np.mean(widths)) if widths else 0,
        PgFeature.pg_num_scan: num_scan,
        PgFeature.pg_num_join: num_join,
        PgFeature.pg_num_sort: num_sort,
        PgFeature.pg_num_agg: num_agg,
        PgFeature.pg_num_temp: num_temp,
        PgFeature.pg_num_select: num_select,
        PgFeature.pg_scan_act_card_sum: scan_act_sum,
        PgFeature.pg_scan_has_filter: scan_has_filter,
        PgFeature.pg_filter_and_count: filter_and,
        PgFeature.pg_filter_or_count: filter_or,
        PgFeature.pg_filter_compare_count: filter_compare,
        PgFeature.pg_filter_like_count: filter_like,
        PgFeature.pg_filter_in_count: filter_in,
        PgFeature.pg_table_id_sum: table_id_sum,
        PgFeature.pg_pipeline_num_ops: len(pipeline_op_ids),
        PgFeature.pg_pipeline_root_act_card: root_act_card,
    }
    for i, f in enumerate(_pg_feature_list()):
        vec[i] = values.get(f, 0)
    return vec


def _get_root_act_card(plan: dict) -> float:
    """Root node's act_card from plan['plan'] and its pg payload."""
    root = plan.get("plan") or {}
    pg = root.get("pg") or {}
    return max(0, float(pg.get("act_card", pg.get("est_card", 0))))


_N_PG_FEATURES = len(PgFeature)
_N_OP_FEATURES = len(_pg_enumerate_operator_features())


class PgFeatureMapper:
    """
    Builds pipeline-level feature vectors from a T3 plan dict that has 'pg' (plan_parameters)
    on each node. Same interface as FeatureMapper for get_pipeline_estimation_matrix and
    get_pipeline_scan_sizes so zeroshot training/eval can swap the mapper.
    """

    n_features = _N_PG_FEATURES + _N_OP_FEATURES

    @staticmethod
    def get_names() -> list[str]:
        base = [f.name for f in _pg_feature_list()]
        op_names = [
            f"{op_key}_{fn}"
            for op_key, fn in _pg_enumerate_operator_features()
        ]
        return base + op_names

    def get_empty_feature_vector(self) -> np.ndarray:
        return np.zeros(self.n_features, dtype=float)

    def get_pipeline_estimation_matrix(self, plan: dict) -> np.ndarray:
        """
        Return one feature vector per pipeline. plan must have 'plan' (root node with
        analyzePlanId and 'pg' on each node) and 'analyzePlanPipelines' (list of
        {operators: [analyzePlanIds], duration, ...}).
        """
        root_node = plan.get("plan")
        pipelines_list = plan.get("analyzePlanPipelines") or []
        if not root_node or not pipelines_list:
            return np.zeros((0, self.n_features), dtype=float)

        id_to_node: dict[int, dict] = {}
        _collect_nodes_by_id(root_node, id_to_node)
        root_act_card = _get_root_act_card(plan)

        rows = []
        for pl in pipelines_list:
            op_ids = pl.get("operators") or []
            base_row = _extract_pipeline_pg_features(op_ids, id_to_node, root_act_card)
            op_row = _extract_operator_features(op_ids, id_to_node, root_node)
            rows.append(np.concatenate([base_row, op_row]))
        if not rows:
            return np.zeros((0, self.n_features), dtype=float)
        return np.vstack(rows)

    @staticmethod
    def get_pipeline_scan_sizes(plan: dict) -> np.ndarray:
        """
        Pipeline scan size for per-tuple target and for converting per-tuple prediction
        back to runtime. Experiment variant: 1.0 for every pipeline (no scan-card sum).

        The previous implementation summed act_card of scan operators per pipeline (min 1);
        restore that if you need the PG scan-based scaling again.
        """
        root_node = plan.get("plan")
        pipelines_list = plan.get("analyzePlanPipelines") or []
        if not root_node or not pipelines_list:
            return np.array([], dtype=float)
        return np.ones(len(pipelines_list), dtype=float)
