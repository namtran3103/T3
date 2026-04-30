"""
Monkey-patch PgFeatureMapper.get_pipeline_scan_sizes for tuple-level experiments.

The default implementation returns constant 1.0 per pipeline (pipeline-level variant).
This module replaces it with the Umbra-like scan-cardinality version: sum of act_card
across scan operators per pipeline, falling back to the first-operator cardinality when
no scan operator is present.

Call apply_patch() once at the top of any script that needs tuple-level behaviour,
before any training or inference code runs.

Importable from any script that adds this directory to sys.path:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                              / "models" / "0_reproduction" / "tuple"))
    import patch_scan_sizes
    patch_scan_sizes.apply_patch()
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_here = Path(__file__).resolve().parent          # 0_reproduction/tuple/
_repo = _here.parent.parent.parent.parent  # T3 root
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.pg_features import (
    PG_OP_SCAN,
    PgFeatureMapper,
    _collect_nodes_by_id,
    _get_child_act_card,
    _get_pipeline_ops_in_execution_order,
)


def _tuple_level_get_pipeline_scan_sizes(plan: dict) -> np.ndarray:
    """
    Get the pipeline scan sizes for each pipeline.
    Look at the scan operators in the plan and get the sum of the act_card of the scan operators.
    One or zero scan operators per pipeline.

    If there is no scan operator (no scan rows / zero sum), mirror Umbra core
    ``Pipeline.get_pipeline_scan_cardinality``: take the first pipeline operator in
    execution order (post-order leaf in the plan subtree); if it is Sort, an
    Aggregate variant, Hash, or Materialize, use its output cardinality (act_card);
    else use its input cardinality (child cards, same probe/build convention as
    ``_extract_operator_features`` for joins).
    """
    root_node = plan.get("plan")
    pipelines_list = plan.get("analyzePlanPipelines") or []
    if not root_node or not pipelines_list:
        return np.array([], dtype=float)

    id_to_node: dict[int, dict] = {}
    _collect_nodes_by_id(root_node, id_to_node)

    # Matches OperatorType.GroupBy, Sort, Temp in operator_stages.get_pipeline_scan_cardinality
    breaker_first_ops = (
        "Sort",
        "Aggregate",
        "Partial Aggregate",
        "Finalize Aggregate",
        "Hash",
        "Materialize",
    )

    def _umbra_like_first_op_size(op_ids: list[int]) -> float:
        ordered = _get_pipeline_ops_in_execution_order(op_ids, id_to_node, root_node)
        if not ordered:
            return 0.0
        _, node = ordered[0]
        pg = node.get("pg") or {}
        op_name = (pg.get("op_name") or "").strip()
        act_card = max(0, float(pg.get("act_card", pg.get("est_card", 0))))
        left_card = _get_child_act_card(node, "left", id_to_node)
        right_card = _get_child_act_card(node, "right", id_to_node)
        input_card = _get_child_act_card(node, "input", id_to_node)
        if op_name in ("Hash Join", "Merge Join"):
            in_card = right_card
        else:
            in_card = input_card if input_card > 0 else left_card
        if in_card <= 0 and op_name in PG_OP_SCAN:
            in_card = act_card
        if op_name in breaker_first_ops:
            return float(act_card)
        return float(in_card)

    sizes: list[float] = []
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
                scan_sum += max(
                    0, float(pg.get("act_card", pg.get("est_card", 0)))
                )
        if scan_sum > 0:
            sizes.append(max(1.0, scan_sum))
        else:
            sizes.append(_umbra_like_first_op_size(op_ids))

    return np.array(sizes, dtype=float)


def apply_patch() -> None:
    """Replace PgFeatureMapper.get_pipeline_scan_sizes with the tuple-level implementation."""
    PgFeatureMapper.get_pipeline_scan_sizes = staticmethod(
        _tuple_level_get_pipeline_scan_sizes
    )
