# Execution Flow: `training_zeroshot_tpch_holdout.py`

This document explains, step by step, which methods are executed when you run:

```bash
python -m src.zeroshot.training_zeroshot_tpch_holdout
```

It follows the current code in `src/zeroshot/training_zeroshot_tpch_holdout.py`.

## 1) Module import phase (before `main`)

When Python imports the module, these top-level actions happen first:

1. Standard modules are imported (`argparse`, `logging`, `sys`, `Path`).
2. `_repo` is computed and inserted into `sys.path` (if missing).
3. Third-party modules are imported (`numpy`, `lightgbm`, `train_test_split`).
4. Project modules are imported:
   - `q_error`
   - `PerTupleTreeModel`
   - `PgFeatureMapper`
   - `BenchmarkedQuery`, `QueryCategory`
   - `QueryPlan`
   - from `zeroshot_to_t3`: `get_minimal_database`, `load_zeroshot_json`, `zeroshot_plan_to_t3`, `collect_all_zeroshot_jsons`
5. Constants are defined (`SEED`, `HOLDOUT_BENCHMARK`, defaults for data/model path).

## 2) Entrypoint

Execution enters:

1. `if __name__ == "__main__":`
2. `main()`

## 3) Inside `main()` (high-level order)

`main()` executes these methods in this order:

1. `argparse.ArgumentParser(...)`
2. `parser.add_argument(...)` (called 5 times)
3. `parser.parse_args()`
4. `args.data.resolve()`
5. `data_dir.is_dir()` check
   - If false: print + `sys.exit(1)`
6. `collect_all_zeroshot_jsons(data_dir)`
   - If empty: print + `sys.exit(1)`
7. `split_train_test_by_holdout(all_json_paths, holdout_name=args.holdout)`
8. Train-path check
   - If empty: print + `sys.exit(1)`
9. `load_benchmarked_queries_from_zeroshot(train_paths, use_actual_card=...)`
   - If empty: print + `sys.exit(1)`
10. `train_per_tuple_model(train_queries, seed=args.seed)`
11. `next_available_model_path(_repo, base_out)`
12. `bst.save_model(...)`
13. If `test_paths` is non-empty:
    - `load_benchmarked_queries_from_zeroshot(test_paths, ...)`
    - For each test query:
      - `model.estimate_runtime(b)`
      - `b.get_total_runtime()`
      - `q_error(actual, pred)`
    - `np.mean`, `np.median`, `np.percentile` for summary
    - append summary line to `holdout.txt`
14. Else: print "No test files ..."

## 4) Detailed call flow for `load_benchmarked_queries_from_zeroshot(...)`

For both train and test loading, the same function executes:

1. `get_minimal_database()`
2. For each JSON file path `jf`:
   1. `load_zeroshot_json(jf)`
   2. `data.get("parsed_plans", [])`
   3. For each parsed plan `zs_plan`:
      1. `zeroshot_plan_to_t3(zs_plan, use_actual_card=...)`
      2. `converted.get("plan_runtime_seconds")`
      3. `QueryPlan(converted, db, predicted_cardinalities=...)`
      4. `plan.build_pipelines(converted["analyzePlanPipelines"])`
      5. `BenchmarkedQuery(plan, [runtime_sec], name, ..., plan_dict=converted)`
3. Return list of `BenchmarkedQuery`.

If conversion/build fails for a plan, it logs and skips that plan.

## 5) Detailed call flow inside `zeroshot_plan_to_t3(...)`

This function comes from `src/zeroshot/zeroshot_to_t3.py`. For each parsed plan:

1. `_convert_node(zs_plan, next_id, use_actual_card)`
   - Recursively maps zero-shot operators to T3/Umbra nodes.
   - During recursion, helper methods may run:
     - `_get_card(...)`
     - `_get_width(...)`
     - `_convert_filter_columns_to_tree(...)`
     - `_filter_operator_to_expression(...)`
     - `_make_placeholder(...)` (for missing children)
2. `_assign_pipelines(root_umbra, pipeline_by_id, [0], [1])`
   - Recursively assigns pipeline IDs.
   - May call `_assign_pipelines_children(...)` and `_is_pipeline_breaker(...)`.
3. `_fill_times_zeroshot(zs_plan, root_umbra, times_by_id)`
   - Recursively attaches start/stop timings per node.
   - Uses `_get_start_stop_us(...)`.
4. Build `pipelines_list` from `pipeline_by_id` + `times_by_id`.
5. Build final dict with:
   - `"plan"`
   - `"ius"`
   - `"analyzePlanPipelines"`
   - optional `"plan_runtime_seconds"`

## 6) Detailed call flow for `train_per_tuple_model(...)`

Called once after training queries are loaded:

1. `PgFeatureMapper()`
2. `train_test_split(np.arange(len(queries)), test_size=0.2, random_state=seed)`
3. Build training pipeline rows:
   - For each train query:
     - `query.get_per_tuple_pipeline_runtime_data(feature_mapper)`
     - keep rows with non-zero feature vector (`np.any(x != 0)`)
4. Transform targets:
   - `np.vstack(...)`, `np.array(...)`
   - `np.maximum(y_train, 1e-15)`
   - `-np.log(y_train)`
5. Build validation rows similarly.
6. Create LightGBM datasets:
   - `lgb.Dataset(...)` for train
   - `lgb.Dataset(...)` for val
7. Train booster:
   - `lgb.Booster(param, train_data)`
   - `bst.add_valid(val_data, "val_data")`
   - loop `num_trees` times: `bst.update()`
8. Return:
   - `PerTupleTreeModel(bst, feature_mapper=feature_mapper)`
   - raw `bst`

## 7) Detailed call flow for output model naming

`next_available_model_path(_repo, base_out)`:

1. Resolve absolute path.
2. If path does not exist -> return as-is.
3. Else try: `_v1`, `_v2`, `_v3`, ... until a free filename is found.
4. Return the first free path.

## 8) Detailed call flow for test evaluation branch

Only executed if holdout/test files exist and load successfully:

1. `load_benchmarked_queries_from_zeroshot(test_paths, ...)`
2. For each `BenchmarkedQuery b`:
   1. `model.estimate_runtime(b)`
   2. `b.get_total_runtime()`
   3. `q_error(actual, pred)`
3. Aggregate metrics:
   - `np.mean(errors)`
   - `np.median(errors)`
   - `np.percentile(errors, 90)`
   - `min(errors)`, `max(errors)`
4. Append one summary line to `holdout.txt`.

## 9) `pg_features.py`: what runs when

This is the execution order for `src/pg_features.py` in the same training run.

### 9.1 Import-time execution (runs once when module is imported)

1. Constants/enums/classes are defined (`PG_OP_*`, `PgOpFeature`, `PgFeatureDim`, `PgFeature`, `PgFeatureMapper`).
2. `_N_PG_FEATURES = len(PgFeature)`.
3. `_N_OP_FEATURES = len(_pg_enumerate_operator_features())`.
   - `_pg_enumerate_operator_features()` runs once at import.
   - It repeatedly calls `_pg_op_name_to_feature_key(...)` and `_pg_op_feature_dim_to_features(...)`.

### 9.2 Runtime execution during model training/evaluation

In `train_per_tuple_model(...)`, `query.get_per_tuple_pipeline_runtime_data(feature_mapper)` triggers the mapper flow below.

Main runtime method:

1. `PgFeatureMapper.get_pipeline_estimation_matrix(plan)`
2. `_collect_nodes_by_id(root_node, id_to_node)` (recursive tree walk)
3. `_get_root_act_card(plan)`
4. For each pipeline:
   1. `_extract_pipeline_pg_features(op_ids, id_to_node, root_act_card)`
      - may call `_count_filter_columns(...)` for scan filter trees
   2. `_extract_operator_features(op_ids, id_to_node, root_node)`
      - `_get_pipeline_ops_in_execution_order(...)`
      - `_pg_enumerate_operator_features(...)`
      - `_get_child_act_card(...)`
      - optional `_count_filter_columns(...)`
      - `_pg_op_name_to_feature_key(...)`
   3. `np.concatenate([base_row, op_row])`
5. `np.vstack(rows)` returned as the pipeline feature matrix.

Related runtime method (used for per-tuple reconstruction):

1. `PgFeatureMapper.get_pipeline_scan_sizes(plan)`
2. `_collect_nodes_by_id(...)`
3. Per pipeline/operator scan-card sum
4. return `np.array(...)`

Optional utility methods (called only when needed):

- `PgFeatureMapper.get_names()` -> `_pg_feature_list()` + `_pg_enumerate_operator_features()`
- `PgFeatureMapper.get_empty_feature_vector()` -> `np.zeros(...)`

## 10) Early-exit branches

Execution stops early with `sys.exit(1)` in these cases:

1. `--data` is not a directory.
2. No JSON files found below `--data`.
3. Train split is empty (all files match holdout).
4. No training queries could be loaded.

---

If you want, I can also add a **sequence diagram** (Mermaid) showing the same call chain visually.
