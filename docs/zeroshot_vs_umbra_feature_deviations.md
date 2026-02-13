# Zero-shot vs Umbra: feature source and deviation analysis

This document maps how **every feature** used by the core (T3/Umbra path) is computed, what the **Umbra plan JSON** provides, and where the **zero-shot mapper** deviates (insufficient or too much).

Reference: `src/features.py` (FeatureMapper.get_estimation_vector), `src/query_plan.py` (QueryPlan), `src/operator_stages.py` (Pipeline, ExecutionPhase). Example Umbra plan: `data/tpchSf1/fixed/tpchSf1_q5.json`. Terminal dump: `python -m testing.run_umbra_prediction --plan-json data/tpchSf1/fixed/tpchSf1_q5.json --db tpchSf1 -v`.

---

## 1. How features are computed in the core (Umbra path)

- **Cardinalities**: From `query_plan.py`: `_get_output_cardinality` (uses `cardinality` / `analyzePlanCardinality`), `_get_input_cardinality` (TableScan: `inputCardinality` or schema; unary: walk `input`; join: left child output), `_get_right_cardinality` (right child output).
- **Tuple sizes**: `_get_tuple_size(op)` = sum of `producedIUs` (either `iu["estimatedSize"]` or lookup in plan-level `ius`).
- **Percentages**: In `operator_stages.py`: `input_percentage` = `input_cardinality / pipeline_scan_cardinality`, and similarly for output and right. `pipeline_scan_cardinality` = first operator’s **input_cardinality** (for scan-like) or **output_cardinality** (GroupBy/Sort/Temp).
- **Expressions** (TableScan only): `_list_expressions(op)` uses `op["restrictions"]` and `op["residuals"]`; for each entry, `_featurize_expression` (counts/types) and `_get_expression_selectivity` (selectivity). Only TableScan runs this; the result is the `Expressions` used in the feature vector (e.g. like_percentage, compare_percentage, between_percentage, in_expression_percentage, or_exp_percentage, starts_with_percentage).

So the plan must provide, per node: `operator`, `physicalOperator`, `operatorId`, `analyzePlanId`, `cardinality`, `analyzePlanCardinality`, `left`/`right`/`input`, `producedIUs`; for TableScan also `inputCardinality` (or tablename for schema fallback), `restrictions`, `residuals`. Top-level: `plan` (root), `ius`, `analyzePlanPipelines` (operators, start, stop).

---

## 2. Plan wrapper (top-level)

| Key | Umbra | Zeroshot | Deviation |
|-----|--------|----------|-----------|
| `plan` | Root operator dict (nested) | Same (converted from zero-shot tree) | Aligned |
| `ius` | List of `{ "iu": "<name>", "estimatedSize": <bytes> }` per produced column | Single entry `{ "iu": "default", "estimatedSize": MIN_IU_BYTES }` | **Insufficient**: Zeroshot does not emit per-IU sizes; all operators use a single default IU. Tuple size is still set per-operator via `producedIUs` on the node (see below). |
| `analyzePlanPipelines` | `[{ "operators": [analyzePlanIds], "start", "stop", "duration" }]` | Same shape; `start`/`stop` from zero-shot `plan_parameters` (act_startup_cost, act_time) | Aligned (units/semantics may differ; only operator IDs and start/stop are used by build_pipelines). |

---

## 3. Per-operator: cardinalities and IDs

Core reads:

- **Output cardinality**: `_get_output_cardinality(op, predicted_cardinalities)` — uses `op["cardinality"]` for tablescan; else `op["analyzePlanCardinality"]` when `not predicted_cardinalities`, else `op["cardinality"]`.
- **Input cardinality**: `_get_input_cardinality` — TableScan: `op["inputCardinality"]` if present, else `db.schema.get_table_scan_size(tablename)`; unary: walks `op["input"]` until a node with `cardinality` or `analyzePlanCardinality`; join: left child’s output.
- **Right cardinality** (joins): `_get_right_cardinality` → output cardinality of `op["right"]`.
- **Left cardinality**: `_get_left_cardinality` → `op["left"]["cardinality"]` or `op["left"]["analyzePlanCardinality"]` depending on `predicted_cardinalities`.

| Source | Umbra | Zeroshot | Deviation |
|--------|--------|----------|-----------|
| `operator`, `physicalOperator` | Present (e.g. sort, groupby, join, hashjoin, tablescan) | Mapped from zero-shot op_name | Aligned |
| `operatorId`, `analyzePlanId` | Both set (pipeline mapping uses analyzePlanId) | Both set to same id | Aligned |
| `cardinality`, `analyzePlanCardinality` | Both on every node | Both set (`_get_card`) | Aligned |
| `left` / `right` / `input` | Nested operator dicts with same keys | Same structure from _convert_node recursion | Aligned |
| TableScan `inputCardinality` | Real table size (or from plan) | **Real** only when enrichment provides `input_cardinality` (1 ≤ value < 1e15); otherwise **1** (Option B: no planner estimates for non-enriched scans) | **Aligned** when enriched; else 1 for consistent features. |
| TableScan `tablename` | Real table name | `"unknown"` | **Insufficient** for schema-based input cardinality fallback; with inputCardinality set, core does not use tablename for cardinality. |

---

## 4. Per-operator: tuple sizes (in_size, out_size)

- **Output size**: `_get_tuple_size(op)` = sum over `op["producedIUs"]` of `iu["estimatedSize"]` (or lookup in `self.ius` when entry is a string).
- **Input size**: same for `phase.operator.input_op.output_tuple_size` (child’s producedIUs).

| Source | Umbra | Zeroshot | Deviation |
|--------|--------|----------|-----------|
| `producedIUs` | List of **IU names** (strings); sizes in plan-level `ius` | List of one dict: `[{ "estimatedSize": int(width) }]` from `_get_width(zs_node)` | **Different shape**: Zeroshot provides one aggregate size per node; Umbra provides per-column sizes. Core sums both; one number per node is sufficient for current features. Possible **insufficient** if future features use per-column sizes. |

---

## 5. Pipeline and percentage features

- **pipeline_scan_cardinality**: `Pipeline.get_pipeline_scan_cardinality()` = first operator’s **input_cardinality** (for scan-like) or **output_cardinality** (GroupBy/Sort/Temp).
- **input_percentage**: `operator.input_cardinality * fraction / pipeline_scan_cardinality`.
- **output_percentage**: `operator.output_cardinality * fraction / pipeline_scan_cardinality`.
- **right_percentage**: `operator.right_input_cardinality * fraction / pipeline_scan_cardinality`.

All percentage features therefore depend on (1) each operator’s cardinalities and (2) the first operator’s input (or output) cardinality. Zeroshot now uses real `inputCardinality` when enrichment provides `input_cardinality`, so pipeline_scan_cardinality and percentages align with Umbra for enriched plans; when not enriched, fallback remains 1.

---

## 6. Expression / selectivity features (TableScan only)

- **Source**: `_parse_expressions` → `_list_expressions(op)` → `op["restrictions"]` and `op["residuals"]`; then `_featurize_expression` and `_get_expression_selectivity` per expression.
- **Features**: like_percentage, compare_percentage, in_expression_percentage, between_percentage, or_exp_percentage, starts_with_percentage (and counts; counts are not used in the current feature vector per get_dim_features).

**Umbra restriction shape (example from tpchSf1_q5):**

- Top-level restriction can be wrapped: `{ "attribute", "mode": "filter", "value": { "expression": "and", "input": [ ... ], "estimatedSelectivity": 0.208... } }`.
- **Core**: `_featurize_expression` unwraps `mode == "filter"` and recurses on `expression["value"]`. `_get_expression_selectivity(expression)` does **not** unwrap; it expects `expression` to have either `"estimatedSelectivity"` or `"expression"` (and, or, compare, between, in, etc.). So when the **wrapper** is passed to `_get_expression_selectivity`, the core would not see `estimatedSelectivity` (it’s inside `value`). So Umbra’s **estimatedSelectivity can be unused** unless the loader unwraps restrictions before parsing.
- **Zeroshot**: Emits a **single** restriction per scan = one nested tree with `expression`, `input`, and optional `direction`; **no** top-level `mode`/`value` wrapper. When enrichment provides `overall_selectivity`, it is set **at the root** of that tree. So `_get_expression_selectivity` receives the root node and can use `estimatedSelectivity` directly. **Aligned** with what the core expects for selectivity.

**Restriction content:**

- Zeroshot: `_convert_filter_columns_to_tree` builds nodes with `expression` (and, or, not, compare, like, in, between, startswith, isnotnull) and `input` / `direction`; root can have `estimatedSelectivity`.
- Umbra: Richer (e.g. iuref, const); core only cares about expression type and direction for featurization and default selectivities. Zeroshot does not emit extra Umbra-only keys (e.g. attribute, collate); core does not require them. **Aligned** for feature computation.

---

## 7. Placeholder and missing operators

- Zeroshot uses `_make_placeholder` for missing children: tablescan with cardinality 0, `inputCardinality` 1, empty restrictions/residuals. Core can parse this; yields zero output and trivial percentages. **Aligned**.
- Operators Zeroshot maps to “select” (e.g. Gather, Limit, Append): core treats them as pass-through; no expression parsing. **Aligned**.

---

## 8. Summary: deviations

| Area | Deviation | Type | Notes |
|------|-----------|------|--------|
| Plan-level `ius` | Single default IU only | Insufficient | Per-operator tuple size still via node `producedIUs`; no per-column IU list. |
| TableScan `inputCardinality` | Real when enriched | Aligned | Use enriched `input_cardinality` when available; otherwise fallback to 1. |
| TableScan `tablename` | "unknown" | Insufficient | Only matters if inputCardinality were omitted; currently not used for cardinality. |
| `producedIUs` | One `{ estimatedSize }` per node | Different | Semantically sufficient for in/out size features; no per-column breakdown. |
| Restrictions | No mode/filter wrapper; root estimatedSelectivity | Aligned | Zeroshot shape matches what _get_expression_selectivity uses; Umbra wrapper would need unwrapping for selectivity. |

---

## 9. Recommendation for zeroshot as “mapper only”

- **Keep**: Plan/operator structure, cardinality/analyzePlanCardinality, left/right/input, operatorId/analyzePlanId, physicalOperator, single restriction tree per scan with optional root estimatedSelectivity, producedIUs as one size per node, real inputCardinality when enrichment provides `input_cardinality`, tablename = "unknown" for scans, analyzePlanPipelines with operator IDs and start/stop.
- **Do not add**: Per-IU list at plan level (unless core is extended to use it), or Umbra-specific restriction wrapper (mode/filter/value) unless the core is changed to unwrap in _get_expression_selectivity.
- **Optional later**: If the core is updated to unwrap `mode: "filter"` in _get_expression_selectivity and use estimatedSelectivity from Umbra’s `value`, zeroshot could optionally emit the same wrapper for maximum compatibility; currently zeroshot’s unwrapped root selectivity is the one that is actually used.
