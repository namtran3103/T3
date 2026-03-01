# PG features (zeroshot-native feature set)

This document describes the **Postgres/zeroshot-native feature set** used for training and evaluating T3 on parsed_plans (e.g. from `zero-shot-data/runs/parsed_plans`). These features are defined in `src/pg_features.py` and are used instead of the Umbra `FeatureMapper` when working with zeroshot data.

---

## 1. Purpose

- **Semantic match:** Umbra features assume `input_card`, `output_card`, and `pipeline_scan_cardinality`. For zeroshot we often have only **output** cardinality on scans (no table size), no schema, and pipeline scale is wrong. PG features use only what parsed_plans provide.
- **Single responsibility:** Zeroshot training and inference use PG features only; Umbra/Postgres-with-schema keep using `src/features.FeatureMapper`. No mixing of two semantics in one vector.

---

## 2. Data source

Features are derived from the **`pg`** payload attached to each node in the T3-converted plan. The zeroshot mapper (`zeroshot_to_t3._convert_node`, `augmented_zeroshot_to_t3._convert_node`) sets `out["pg"] = dict(plan_parameters)` so every node carries the original parsed_plans fields.

**Per-node fields used (from `plan_parameters` / `pg`):**

| Field | Meaning | Used for |
|-------|--------|----------|
| `op_name` | PG operator name | Operator-type counts (scan, join, sort, agg, temp, select) |
| `est_card` | Planner estimated output rows | Cardinality sum/max; scan card sum |
| `act_card` | Actual output rows | Cardinality sum/max; scan card sum; root act_card |
| `est_width` | Estimated tuple width (bytes) | Width avg |
| `act_time` | Actual time for node (ms) | Time sum/max |
| `act_startup_cost` | Startup time (ms) | Time sum |
| `table` | Table id (scans) | pg_table_id_sum |
| `filter_columns` | Filter tree (operator, children) | Filter counts (AND, OR, compare, like, in, between); has_filter |
| `overall_selectivity` | From enrichment (optional) | pg_overall_selectivity_sum |

Pipeline structure comes from `analyzePlanPipelines` (operator ids per pipeline, duration in seconds). Root node’s `act_card` is used for `pg_pipeline_root_act_card`.

---

## 3. Feature list (PgFeature enum)

All features are **aggregated per pipeline** (one vector per pipeline). The vector has fixed length; missing data (e.g. no filter) is 0.

### 3.1 Cardinality (all ops in pipeline)

| Feature | Description |
|---------|-------------|
| `pg_est_card_sum` | Sum of `est_card` over all operators in the pipeline |
| `pg_est_card_max` | Max of `est_card` over all operators |
| `pg_act_card_sum` | Sum of `act_card` over all operators |
| `pg_act_card_max` | Max of `act_card` over all operators |

### 3.2 Time (ms)

| Feature | Description |
|---------|-------------|
| `pg_act_time_sum` | Sum of `act_time` over all operators |
| `pg_act_time_max` | Max of `act_time` over all operators |
| `pg_act_startup_sum` | Sum of `act_startup_cost` over all operators |

### 3.3 Width

| Feature | Description |
|---------|-------------|
| `pg_est_width_avg` | Mean of `est_width` over all operators |

### 3.4 Operator-type counts

| Feature | Description |
|---------|-------------|
| `pg_num_scan` | Number of operators with `op_name` in Seq Scan, Parallel Seq Scan, Index Scan, Index Only Scan |
| `pg_num_join` | Number of operators with `op_name` in Hash Join, Merge Join, Nested Loop |
| `pg_num_sort` | Number of Sort operators |
| `pg_num_agg` | Number of Aggregate, Partial Aggregate, Finalize Aggregate |
| `pg_num_temp` | Number of Hash, Materialize |
| `pg_num_select` | Number of Gather, Memoize, Limit, Append, Subquery Scan, Bitmap Heap/Index Scan; plus any other op not in the above groups |

### 3.5 Scan-specific

| Feature | Description |
|---------|-------------|
| `pg_scan_act_card_sum` | Sum of `act_card` over **scan** operators only in the pipeline |
| `pg_scan_est_card_sum` | Sum of `est_card` over **scan** operators only |
| `pg_scan_has_filter` | 1 if any scan in the pipeline has non-empty `filter_columns`, else 0 |

### 3.6 Filter structure (from `filter_columns` tree on scans)

Counts are computed by recursively walking the filter tree (operator, children). AND/OR recurse; leaf operators are counted.

| Feature | Description |
|---------|-------------|
| `pg_filter_and_count` | Total count of AND nodes in all scan filters in the pipeline |
| `pg_filter_or_count` | Total count of OR nodes |
| `pg_filter_compare_count` | Total count of comparison leaves (=, &lt;, &gt;, etc.) |
| `pg_filter_like_count` | Total count of LIKE |
| `pg_filter_in_count` | Total count of IN |
| `pg_filter_between_count` | Total count of BETWEEN |

### 3.7 Enrichment / table signal

| Feature | Description |
|---------|-------------|
| `pg_overall_selectivity_sum` | Sum of `overall_selectivity` over scans that have it; 0 if none |
| `pg_table_id_sum` | Sum of `table` id over scans (0 when not present) |

### 3.8 Pipeline-level

| Feature | Description |
|---------|-------------|
| `pg_pipeline_act_time_ms` | Pipeline duration in ms (from `analyzePlanPipelines[].duration` in seconds × 1000) |
| `pg_pipeline_num_ops` | Number of operator ids in this pipeline |
| `pg_pipeline_root_act_card` | Root node’s `act_card` (same for all pipelines of the same plan) |

---

## 4. Computation

- **Module:** `src/pg_features.py`
- **Entry:** `PgFeatureMapper.get_pipeline_estimation_matrix(plan_dict)`
  - Input: T3 plan dict with `plan` (root node tree) and `analyzePlanPipelines` (list of `{ operators: [analyzePlanIds], duration }`).
  - Builds a map `analyzePlanId → node` by walking `plan["plan"]`.
  - For each pipeline, collects the set of operator ids, looks up each node’s `pg` payload, and aggregates into one vector in `PgFeature` enum order.
- **Filter counts:** `_count_filter_columns(filter_columns)` recursively counts AND, OR, compare, like, in, between (and treats NOT/STARTSWITH/IS NOT NULL as compare where applicable).
- **Pipeline scan size:** `PgFeatureMapper.get_pipeline_scan_sizes(plan_dict)` returns, per pipeline, the sum of `act_card` over scan operators (minimum 1). Used for per-tuple targets and for converting per-tuple prediction back to runtime.

---

## 5. When PG features are used

- **Training:** All zeroshot training scripts use `PgFeatureMapper()` and build `BenchmarkedQuery` with `plan_dict=converted`. Examples: `training_zeroshot.py`, `training_zeroshot_tpch_holdout.py`, `training_zeroshot_tpch_holdout_augmented.py`, `training_zeroshot_holdout_fewshot.py`, and raw-holdout scripts that convert via zeroshot.
- **Evaluation:** Scripts that load zeroshot-trained models (e.g. `eval_imdb_full.py`, `eval_imdb_job_light.py`) instantiate the model with `PerTupleTreeModel(booster, feature_mapper=PgFeatureMapper())` so predictions use the same feature vector.
- **Feature matrix:** When `get_feature_matrix(feature_mapper)` is called with a `PgFeatureMapper` and the query has `plan_dict` set, the matrix is computed from `plan_dict` via `feature_mapper.get_pipeline_estimation_matrix(plan_dict)` (no Umbra path, no caching under the Umbra key).
- **Per-tuple target:** When the mapper is `PgFeatureMapper` and `plan_dict` is set, `get_per_tuple_pipeline_runtimes(feature_mapper)` uses `PgFeatureMapper.get_pipeline_scan_sizes(plan_dict)` so the per-tuple target is consistent with the PG path.

---

## 6. API summary

| API | Description |
|-----|-------------|
| `PgFeatureMapper.get_names()` | List of feature names in vector order (same as `PgFeature` enum order). |
| `PgFeatureMapper().get_pipeline_estimation_matrix(plan_dict)` | Returns 2D array: one row per pipeline, one column per `PgFeature`. |
| `PgFeatureMapper.get_pipeline_scan_sizes(plan_dict)` | Returns 1D array: per-pipeline scan size (sum of scan `act_card`, min 1). |

---

## 7. Implementation summary

Summary of what was implemented:

**1. `src/pg_features.py`**

- **PgFeature enum:** 31 features (cardinality sum/max, time sum/max, width avg, operator counts for scan/join/sort/agg/temp/select, scan card sum, filter counts, overall_selectivity, table_id, pipeline duration/num_ops/root_act_card).
- **PgFeatureMapper:** `get_pipeline_estimation_matrix(plan_dict)` builds one vector per pipeline from `plan["plan"]` and `analyzePlanPipelines` using `node["pg"]`; `get_names()` and `get_pipeline_scan_sizes(plan_dict)` (scan size = sum of scan act_card per pipeline, min 1).
- **`_count_filter_columns`:** Recursively counts AND/OR/compare/like/in/between in filter_columns trees.
- **`_collect_nodes_by_id`** and **`_extract_pipeline_pg_features`:** Build id→node map and aggregate per-pipeline features.

**2. `src/zeroshot/zeroshot_to_t3.py`**

- In **`_convert_node`:** after building `out`, set `out["pg"] = dict(p)` (copy of plan_parameters).
- In **`_make_placeholder`:** add `"pg": {"op_name": "Unknown", "est_card": 0, "act_card": 0, "est_width": 8, "act_time": 0, "act_startup_cost": 0}`.

**3. `src/zeroshot/augmented_zeroshot_to_t3.py`**

- In **`_convert_node`:** add `out["pg"] = dict(p)` after building out.

**4. `src/optimizer.py`**

- **BenchmarkedQuery:** new optional field `plan_dict: Optional[dict] = None`.
- **`get_feature_matrix(feature_mapper)`:** if mapper is `PgFeatureMapper` and `plan_dict` is set, call `feature_mapper.get_pipeline_estimation_matrix(self.plan_dict)` (no caching).
- **`get_per_tuple_pipeline_runtimes(feature_mapper=None)`:** if mapper is `PgFeatureMapper` and `plan_dict` is set, use `feature_mapper.get_pipeline_scan_sizes(self.plan_dict)` for per-tuple targets.

**5. `src/model.py`**

- **`PerTupleTreeModel.__init__(self, tree, feature_mapper=None)`:** optional `feature_mapper`; if given, use it instead of default `FeatureMapper()`.
- **`estimate_pipeline_runtime`:** if mapper is `PgFeatureMapper` and `query.plan_dict` is set, call `get_pipeline_scan_sizes(query.plan_dict)`.

**6. Zeroshot loaders**

- All `BenchmarkedQuery(...)` calls that use `zeroshot_plan_to_t3` (or augmented) now pass `plan_dict=converted` in: `training_zeroshot.py`, `training_zeroshot_tpch_holdout.py`, `training_zeroshot_tpch_holdout_augmented.py`, `training_zeroshot_holdout_fewshot.py`, `training_raw_holdout_imdb_full.py`.

**7. Zeroshot training and eval**

- **Training:** `training_zeroshot.py`, `training_zeroshot_tpch_holdout.py`, `training_zeroshot_tpch_holdout_augmented.py`, `training_zeroshot_holdout_fewshot.py` use `PgFeatureMapper()`, `PgFeatureMapper.get_names()`, and `PerTupleTreeModel(bst, feature_mapper=feature_mapper)`.
- **Eval:** `eval_imdb_full.py` and `eval_imdb_job_light.py` load the model with `PerTupleTreeModel(booster, feature_mapper=PgFeatureMapper())`.

---

## 8. References

- **Code:** `src/pg_features.py` — `PgFeature`, `PgFeatureMapper`, `_extract_pipeline_pg_features`, `_count_filter_columns`, `_collect_nodes_by_id`
- **Mapper:** `src/zeroshot/zeroshot_to_t3.py` — `out["pg"]` in `_convert_node` and `_make_placeholder`
- **Augmented:** `src/zeroshot/augmented_zeroshot_to_t3.py` — `out["pg"]` in `_convert_node`
- **Usage:** `src/optimizer.py` — `BenchmarkedQuery.plan_dict`, `get_feature_matrix` / `get_per_tuple_pipeline_runtimes` with `PgFeatureMapper`
- **Umbra path:** `docs/zeroshot_vs_umbra_feature_deviations.md` — how the core Umbra feature path works (sections 1–9)
