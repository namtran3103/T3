"""
Postgres/zeroshot-native feature set for parsed_plans.

Builds feature vectors purely from plan_parameters (pg payload) attached to each node
in the T3-converted plan. Used by zeroshot training and inference instead of the
Umbra FeatureMapper when plan_dict is available.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.util import AutoNumber


# PG operator name groups (must match zeroshot_to_t3 op_name values)
PG_OP_SCAN = ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan")
PG_OP_JOIN = ("Hash Join", "Merge Join", "Nested Loop")
PG_OP_SORT = ("Sort",)
PG_OP_AGG = ("Aggregate", "Partial Aggregate", "Finalize Aggregate")
PG_OP_TEMP = ("Hash", "Materialize")
PG_OP_SELECT = ("Gather", "Memoize", "Limit", "Append", "Subquery Scan", "Bitmap Heap Scan", "Bitmap Index Scan")


class PgFeature(AutoNumber):
    """All features derivable from parsed_plans plan_parameters, aggregated per pipeline."""

    # Cardinality (all ops in pipeline)
    pg_est_card_sum = ()
    pg_est_card_max = ()
    pg_act_card_sum = ()
    pg_act_card_max = ()

    # Time (ms)
    pg_act_time_sum = ()
    pg_act_time_max = ()
    pg_act_startup_sum = ()

    # Width
    pg_est_width_avg = ()

    # Operator counts
    pg_num_scan = ()
    pg_num_join = ()
    pg_num_sort = ()
    pg_num_agg = ()
    pg_num_temp = ()
    pg_num_select = ()

    # Scan-specific (only scan ops in pipeline)
    pg_scan_act_card_sum = ()
    pg_scan_est_card_sum = ()
    pg_scan_has_filter = ()

    # Filter structure (from filter_columns tree on scans)
    pg_filter_and_count = ()
    pg_filter_or_count = ()
    pg_filter_compare_count = ()
    pg_filter_like_count = ()
    pg_filter_in_count = ()
    pg_filter_between_count = ()

    # Enrichment (when present)
    pg_overall_selectivity_sum = ()  # sum over scans that have it; 0 if none
    pg_table_id_sum = ()  # sum of table ids (or 0) for scans; placeholder for table signal

    # Pipeline-level (from analyzePlanPipelines and root)
    pg_pipeline_act_time_ms = ()
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
    """Count AND, OR, compare, like, in, between in filter_columns tree. Returns dict of counts."""
    counts = {"and": 0, "or": 0, "compare": 0, "like": 0, "in": 0, "between": 0}
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
    elif op == "LIKE":
        counts["like"] += 1
    elif op == "IN":
        counts["in"] += 1
    elif op == "BETWEEN":
        counts["between"] += 1
    elif op in ("STARTSWITH", "ISNOTNULL", "IS NULL", "IS NOT NULL"):
        counts["compare"] += 1
    return counts


def _extract_pipeline_pg_features(
    pipeline_op_ids: list[int],
    id_to_node: dict[int, dict],
    pipeline_duration_ms: float,
    root_act_card: float,
) -> np.ndarray:
    """Build one fixed-length feature vector for a single pipeline."""
    n_features = len(PgFeature)
    vec = np.zeros(n_features, dtype=float)

    est_cards = []
    act_cards = []
    act_times = []
    act_startups = []
    widths = []
    num_scan = 0
    num_join = 0
    num_sort = 0
    num_agg = 0
    num_temp = 0
    num_select = 0
    scan_act_sum = 0.0
    scan_est_sum = 0.0
    scan_has_filter = 0
    filter_and = 0
    filter_or = 0
    filter_compare = 0
    filter_like = 0
    filter_in = 0
    filter_between = 0
    overall_sel_sum = 0.0
    table_id_sum = 0

    for nid in pipeline_op_ids:
        node = id_to_node.get(nid)
        if node is None:
            continue
        pg = node.get("pg") or {}
        op_name = (pg.get("op_name") or "").strip()

        est_card = max(0, float(pg.get("est_card", 0)))
        act_card = max(0, float(pg.get("act_card", pg.get("est_card", 0))))
        act_time = max(0, float(pg.get("act_time", 0)))
        act_startup = max(0, float(pg.get("act_startup_cost", 0)))
        width = max(0, float(pg.get("est_width", 8)))

        est_cards.append(est_card)
        act_cards.append(act_card)
        act_times.append(act_time)
        act_startups.append(act_startup)
        widths.append(width)

        if op_name in PG_OP_SCAN:
            num_scan += 1
            scan_act_sum += act_card
            scan_est_sum += est_card
            fc = pg.get("filter_columns")
            if fc is not None and (isinstance(fc, dict) or (isinstance(fc, list) and len(fc) > 0)):
                scan_has_filter = 1
            counts = _count_filter_columns(fc) if fc else {}
            filter_and += counts.get("and", 0)
            filter_or += counts.get("or", 0)
            filter_compare += counts.get("compare", 0)
            filter_like += counts.get("like", 0)
            filter_in += counts.get("in", 0)
            filter_between += counts.get("between", 0)
            sel = pg.get("overall_selectivity")
            if sel is not None and 0 <= float(sel) <= 1:
                overall_sel_sum += float(sel)
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
        PgFeature.pg_est_card_sum: sum(est_cards),
        PgFeature.pg_est_card_max: max(est_cards) if est_cards else 0,
        PgFeature.pg_act_card_sum: sum(act_cards),
        PgFeature.pg_act_card_max: max(act_cards) if act_cards else 0,
        PgFeature.pg_act_time_sum: sum(act_times),
        PgFeature.pg_act_time_max: max(act_times) if act_times else 0,
        PgFeature.pg_act_startup_sum: sum(act_startups),
        PgFeature.pg_est_width_avg: float(np.mean(widths)) if widths else 0,
        PgFeature.pg_num_scan: num_scan,
        PgFeature.pg_num_join: num_join,
        PgFeature.pg_num_sort: num_sort,
        PgFeature.pg_num_agg: num_agg,
        PgFeature.pg_num_temp: num_temp,
        PgFeature.pg_num_select: num_select,
        PgFeature.pg_scan_act_card_sum: scan_act_sum,
        PgFeature.pg_scan_est_card_sum: scan_est_sum,
        PgFeature.pg_scan_has_filter: scan_has_filter,
        PgFeature.pg_filter_and_count: filter_and,
        PgFeature.pg_filter_or_count: filter_or,
        PgFeature.pg_filter_compare_count: filter_compare,
        PgFeature.pg_filter_like_count: filter_like,
        PgFeature.pg_filter_in_count: filter_in,
        PgFeature.pg_filter_between_count: filter_between,
        PgFeature.pg_overall_selectivity_sum: overall_sel_sum,
        PgFeature.pg_table_id_sum: table_id_sum,
        PgFeature.pg_pipeline_act_time_ms: pipeline_duration_ms,
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


class PgFeatureMapper:
    """
    Builds pipeline-level feature vectors from a T3 plan dict that has 'pg' (plan_parameters)
    on each node. Same interface as FeatureMapper for get_pipeline_estimation_matrix and
    get_pipeline_scan_sizes so zeroshot training/eval can swap the mapper.
    """

    n_features = len(PgFeature)

    @staticmethod
    def get_names() -> list[str]:
        return [f.name for f in _pg_feature_list()]

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
            # duration in analyzePlanPipelines is in seconds (zeroshot_to_t3)
            duration_sec = float(pl.get("duration", 0))
            duration_ms = duration_sec * 1000.0
            row = _extract_pipeline_pg_features(op_ids, id_to_node, duration_ms, root_act_card)
            rows.append(row)
        if not rows:
            return np.zeros((0, self.n_features), dtype=float)
        return np.vstack(rows)

    @staticmethod
    def get_pipeline_scan_sizes(plan: dict) -> np.ndarray:
        """
        Pipeline scan size for per-tuple target: sum of act_card of scan operators
        in each pipeline. Used when converting per-tuple prediction back to runtime.
        """
        root_node = plan.get("plan")
        pipelines_list = plan.get("analyzePlanPipelines") or []
        if not root_node or not pipelines_list:
            return np.array([], dtype=float)

        id_to_node: dict[int, dict] = {}
        _collect_nodes_by_id(root_node, id_to_node)

        result = []
        for pl in pipelines_list:
            op_ids = pl.get("operators") or []
            scan_sum = 0.0
            for nid in op_ids:
                node = id_to_node.get(nid)
                if node is None:
                    continue
                pg = node.get("pg") or {}
                op_name = (pg.get("op_name") or "").strip()
                if op_name in PG_OP_SCAN:
                    act = pg.get("act_card", pg.get("est_card", 0))
                    scan_sum += max(0, float(act))
            result.append(max(1.0, scan_sum))  # avoid 0 for division
        return np.array(result, dtype=float)
