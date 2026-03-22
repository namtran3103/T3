# Comparison: `src/zeroshot` (PG vectors) vs `src/t3_jh` (Johannes)

This doc compares the two implementations that produced the results in `holdout.txt` (zeroshot) and `holdout_jh.txt` (Johannes), and explains **why older zeroshot runs could look much better** when timing was still in the feature vector.

## Executive summary

- **`PgFeatureMapper` (current):** does **not** put Postgres observed timings (`act_time`, `act_startup_cost`, pipeline `duration`) into the feature vector. Training labels still use measured query/pipeline runtimes via `BenchmarkedQuery` / `get_pipeline_runtimes()` as before.
- **Historical note:** Earlier zeroshot experiments included those timing fields in X, which is highly predictive but **target leakage** for “predict runtime from plan properties.” Results in `holdout.txt` that predate this change reflect that easier setting.
- **Johannes (`src/t3_jh`)** also does not use observed times as inputs; it builds features from cardinalities/sizes/selectivities/operator structure.

Fair apples-to-apples comparisons should use the **no-timing-in-X** `PgFeatureMapper` and **retrained** models (saved `model_zero_*.txt` files list `feature_names=` in the header; old models expect more features than the current mapper produces).

## What the holdout files show

### Zeroshot (`holdout.txt`)

- The file contains multiple experiments; the strongest runs show **very low q-error** (often near \(1.2\)–\(1.6\) p50 and low averages) across many benchmarks.
- Example (imdb_full, “full run new features implementation”): `p50=1.2236`, `avg=1.3235`, `p90=1.6892`.

### Johannes (`holdout_jh.txt`)

- `p50` values are often in the same ballpark (~1.7–2.5 depending on benchmark), but the file shows **catastrophic outliers** (huge `max` and therefore huge `avg`) in some runs.
- Those outliers dominate `avg` and make the implementation look far worse overall even when the median is reasonable.

## Core methodological differences (what’s actually different)

### 1) Input plan representation

- **Zeroshot** converts each parsed plan into a T3 plan dict that retains the original Postgres node payload under a `pg` key, plus a derived `analyzePlanPipelines` list.
  - Training/eval then uses that `plan_dict` directly for feature extraction via `PgFeatureMapper`.
- **Johannes** keeps a Postgres-shaped representation in its own data model (`src/t3_jh/jh_query_plan.py`, `src/t3_jh/jh_dataloader.py`) and constructs pipelines using PG runtime bookkeeping.

### 2) Pipeline construction

- **Zeroshot** pipelines are ultimately taken from the converted plan’s `analyzePlanPipelines` (built during conversion from the parsed plan).
- **Johannes** explicitly derives pipeline boundaries and durations from Postgres runtime fields (`act_time`, plus `left_runtime`/`right_runtime` for joins) in `extract_pipeline_infos` (`src/t3_jh/jh_dataloader.py`).

Both approaches can be reasonable, but they matter less than the next point (features).

### 3) Feature vectors

#### Zeroshot: `PgFeatureMapper`

Zeroshot training uses:

- `train_per_tuple_model(...): feature_mapper = PgFeatureMapper()` in `src/zeroshot/training_zeroshot_tpch_holdout.py`
- Feature extraction code in `src/pg_features.py`

`PgFeatureMapper` includes:

- **Cardinality/width/operator-count inputs**
- **Operator-specific blocks per Postgres operator type** (fixed list of PG operator names and aggregates per pipeline)

It does **not** include observed operator or pipeline runtimes in X.

#### Johannes: `jh_features.FeatureMapper` does not use actual times

Johannes training uses:

- `feature_mapper = FeatureMapper()` in `src/t3_jh/training_jh_holdout.py`
- Feature extraction code in `src/t3_jh/jh_features.py`

The JH feature set is mostly:

- cardinalities / tuple sizes
- pipeline-relative percentages (input/output/right)
- expression selectivity proxies (like/compare/in/between/or/startswith, etc.)
- per-operator/stage aggregated features

Critically: **it does not feed `act_time`/`act_startup_cost`/pipeline durations as inputs**.

### 4) Model + target transform (largely the same)

Both pipelines train a per-tuple model similarly:

- Transform target \(y\) as \(-\log(y)\)
- Predict and invert with `np.exp(-pred)`
- Multiply by `scan_sizes` to get runtime per pipeline, and sum to query runtime

See:

- `src/model.py::PerTupleTreeModel` (zeroshot)
- `src/t3_jh/jh_model.py::PerTupleTreeModel` (Johannes)

So the dramatic difference in **older** comparisons was **not** coming from a different ML model family; it was primarily **inputs** (timing leakage) **plus** JH stability.

## Why historical zeroshot could look “better”

### 1) Timing leakage (when timings were in X)

If the feature vector included Postgres *observed* `act_time` (and pipeline durations), runtime prediction became much easier: the model saw runtime-like signals directly. That explained very low q-errors vs `holdout_jh.txt` in those runs.

### 2) Wider operator coverage and richer signals

`PgFeatureMapper` enumerates many PG operators seen in the dataset and allocates dedicated feature slots per operator, which reduces “unknown operator” collapse and improves generalization across benchmarks.

### 3) The JH pipeline exhibits extreme outliers

`holdout_jh.txt` contains runs where `max` is astronomically large (sometimes \(10^{10}\) scale), which explodes `avg`.

Those outliers can come from:

- unstable scan-size normalization (since prediction is multiplied by `scan_sizes`)
- pipeline/runtime inconsistencies or edge cases that survive loading
- feature sparsity / wrong scaling for certain plan shapes

Even if the median is OK, those failures dominate `avg` and make JH look much worse.

## Recommendations (fair comparison)

- Use **current** `PgFeatureMapper` (no timing in X), **re-train**, and regenerate metrics.
- Report **p50/p90** primarily (robust to outliers), and separately analyze `avg` with outlier clipping so a few failures don’t dominate.
- Keep cardinalities (`act_card` or `est_card` depending on setting), widths, operator counts, filter structure/selectivity proxies — **not** observed operator/pipeline runtimes in X.

## Pointers into the code

- `src/pg_features.py` — `PgFeature`, `PgFeatureMapper`
- `src/zeroshot/training_zeroshot_tpch_holdout.py` — zeroshot training entry
- `src/t3_jh/training_jh_holdout.py` — Johannes training entry
- `src/optimizer.py` — `get_per_tuple_pipeline_runtime_data` (labels vs features)
