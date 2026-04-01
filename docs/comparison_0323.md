# Comparison 0323: Feature Vector Population (`src/zeroshot` vs `t3-Johannes`)

This note compares how feature vectors are populated in:

- `src/zeroshot` (this repo)
- `/Users/namtran/Documents/Studium/TUM Studium Informatik/WiSe 2025:26/BA2/t3-Johannes`

and explains why zeroshot can look better.

## Short answer

`src/zeroshot` training mainly uses `PgFeatureMapper` (`src/pg_features.py`), which builds a PG-native, pipeline-level vector directly from `pg` payload (`plan_parameters`) attached to each node.  
This mapper uses a wider set of operator-specific slots and extra signals (costs, workers, filter tree counts, optional enrichment like `overall_selectivity`), which can make it more predictive than the leaner `t3-Johannes` vectorization.

## 1) How `src/zeroshot` populates the vector

Main path:

1. Input comes from parsed plans (format in `zero-shot-data/runs/parsed_plans`).
2. `src/zeroshot/zeroshot_to_t3.py` converts each node into T3/Umbra-like shape, but stores original PG data in `node["pg"]`.
3. Pipelines are assigned structurally (`_assign_pipelines`) and stored as `analyzePlanPipelines`.
4. Training scripts in `src/zeroshot/*` use `PgFeatureMapper` (not the default `src/features.py` mapper).
5. `PgFeatureMapper.get_pipeline_estimation_matrix(plan_dict)`:
   - builds base pipeline aggregates (`PgFeature.*`), e.g. `pg_act_card_sum`, `pg_est_cost_sum`, `pg_workers_planned_sum`, scan/filter counters
   - builds operator-block features per PG op (`Seq Scan`, `Hash Join`, `Sort`, `Aggregate`, ...)
   - concatenates both into one row per pipeline.

Important signals used by zeroshot mapper:

- PG actual cardinality (`act_card`, with fallback to `est_card`)
- Planner costs (`est_cost`, `est_startup_cost`)
- Width (`est_width`)
- Parallelism (`workers_planned`)
- Filter tree structure from `filter_columns` (AND/OR/compare/like/in counts)
- Optional enrichment (`overall_selectivity`, table id)
- Per-operator feature blocks for a broad PG operator list

Not used as input:

- observed execution times (`act_time`, `act_startup_cost`, pipeline duration) are excluded from X.

## 2) How `t3-Johannes` populates the vector

Main path:

1. Plan stays PG-shaped (`plan_parameters`, PG operator names).
2. `query_plan.py` parses operators and expressions into `Operator` objects.
3. Pipelines are built (from extracted pipeline info) into execution phases and stages.
4. `features.py` (`FeatureMapper`) generates vectors per execution phase, then sums per pipeline.

Important signals in Johannes mapper:

- input/output/right cardinalities
- tuple sizes
- input/output/right percentages inside pipeline
- expression selectivity proxies (like/compare/in/between/or/startswith)
- operator-stage constants and associated dimensions

Compared to zeroshot’s `PgFeatureMapper`, this path is more stage-centric and usually has less PG-specific handcrafted aggregate channels (e.g., no explicit planner-cost sums as dedicated features).

## 3) Simple example

Assume one pipeline contains:

- `Seq Scan` on `title` with filter `kind_id = 1`
- `Hash Join` with build side cardinality 1,000 and probe side cardinality 50,000
- output cardinality 700

### Zeroshot (`PgFeatureMapper`) will populate

- Base pipeline stats:
  - `pg_act_card_sum` += cards of operators in pipeline
  - `pg_est_cost_sum` += planner costs
  - `pg_num_scan` += 1, `pg_num_join` += 1
  - `pg_scan_has_filter` = 1
  - `pg_filter_compare_count` += 1
- Operator blocks:
  - `Seq_Scan_const` += 1, `Seq_Scan_in_card`, `Seq_Scan_out_percentage`, expression percentages
  - `Hash_Join_const` += 1, `Hash_Join_in_card` (probe input), `Hash_Join_right_percentage`, `Hash_Join_out_percentage`

So one pipeline row gets both coarse aggregate signals and fine per-operator slots.

### Johannes (`features.FeatureMapper`) will populate

- For each execution phase (scan/join stage), set:
  - `const`
  - stage-specific cardinality/percentage features
  - expression percentages for scan
- Pipeline row = sum of those phase vectors.

This is clean and principled, but typically less enriched with PG-specific global aggregates such as planner cost totals or explicit `workers_planned`.

## 4) Why zeroshot may perform better (likely)

1. **Richer PG-native feature space**  
   Zeroshot includes extra predictive channels (cost sums/max, workers planned, broader per-op blocks, explicit filter-tree counts).

2. **Better operator coverage for parsed plans**  
   `PgFeatureMapper` enumerates many PG operators seen in parsed plans and has fallback handling, reducing information loss.

3. **Enrichment fields can help**  
   Signals like `overall_selectivity` can improve scan/join difficulty estimation.

4. **Feature design aligned to your exact data source**  
   Zeroshot features are tailored to parsed-plans payload directly (`filter_columns`, `op_name`, planner stats), which often improves fit.

## 5) Caveat for fair comparison

To claim a strict apples-to-apples win, keep these fixed across both pipelines:

- same train/test split
- same target transformation and model settings
- same cardinality mode (`act` vs `est`)
- same outlier handling and evaluation metric focus (`p50`, `p90`, `avg`, `max`)

If you want, I can add a follow-up doc that maps feature-by-feature equivalents between `PgFeatureMapper` and `t3-Johannes/features.py` so you can test an ablation (which specific zeroshot features drive the gain).

