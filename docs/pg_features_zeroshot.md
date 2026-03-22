# PG / zeroshot-native feature set

For **zeroshot training and inference**, the pipeline uses a **dedicated PG feature set** instead of the Umbra FeatureMapper. This avoids the semantic mismatch when scan input cardinality is unknown (e.g. `inputCardinality = 1`) and uses only what parsed_plans provide.

## Module

- **`src/pg_features.py`** — defines `PgFeature` (enum of all PG-derived features) and `PgFeatureMapper`.

## Input

The T3 plan dict returned by `zeroshot_plan_to_t3` (or `augmented_zeroshot_to_t3`) with **`pg`** attached to each node. The zeroshot mapper adds `out["pg"] = dict(plan_parameters)` in `zeroshot_to_t3._convert_node` and in the augmented converter so every node carries the original `plan_parameters` (op_name, est_card, act_card, act_time, est_width, filter_columns, etc.).

## Output

One fixed-length feature vector per pipeline (same interface as `FeatureMapper.get_pipeline_estimation_matrix`). Features are aggregated from `node["pg"]` over the operators in each pipeline:

- Cardinality sum/max (est_card, act_card)
- Planner cost sum/max (`est_cost`) and startup cost sum (`est_startup_cost`) per pipeline
- Sum of `workers_planned` over operators in the pipeline
- Width avg (est_width)
- Operator-type counts: scan, join, sort, agg, temp, select
- Scan-specific: scan card sum, has_filter, filter counts (AND, OR, compare, like, in, between), overall_selectivity sum, table_id sum
- Pipeline-level: num ops, root act_card (no observed operator or pipeline timings in X)

Observed `act_time`, `act_startup_cost`, and pipeline `duration` are **not** used as features; they remain available in parsed plans only where needed for labels and pipeline bookkeeping.

See `PgFeature` in `pg_features.py` for the full list.

## When used

- **Training:** Zeroshot training scripts (`training_zeroshot.py`, `training_zeroshot_tpch_holdout.py`, `training_zeroshot_tpch_holdout_augmented.py`, `training_zeroshot_holdout_fewshot.py`, etc.) use `PgFeatureMapper()` and build `BenchmarkedQuery` with `plan_dict=converted`. `get_feature_matrix(PgFeatureMapper)` then uses `plan_dict` to compute the PG feature matrix.
- **Evaluation:** Scripts that load zeroshot-trained models (e.g. `eval_imdb_full.py`, `eval_imdb_job_light.py`) use `PerTupleTreeModel(booster, feature_mapper=PgFeatureMapper())` so predictions use the same features.
- **Pipeline scan size:** For per-tuple targets and prediction, `PgFeatureMapper.get_pipeline_scan_sizes(plan_dict)` returns the sum of scan `act_card` per pipeline (with a minimum of 1) so the zeroshot path is self-contained.

## References

- `src/pg_features.py` — PgFeature, PgFeatureMapper, _extract_pipeline_pg_features
- `src/zeroshot/zeroshot_to_t3.py` — attachment of `pg` in _convert_node and _make_placeholder
- `docs/zeroshot_vs_umbra_feature_deviations.md` — Umbra feature path (sections 1–9)
