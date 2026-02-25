# T3-Johannes (t3_jh)

Train and evaluate T3 on **parsed_plans** (e.g. `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans`) using the **Johannes-style pipeline**: PG-style plan with `plan_parameters` / `children`, `rewrite_children`, pipeline extraction, per-tuple LightGBM. No dependency on `src.zeroshot`; logic mirrors the t3-Johannes repo.

## Data

- **Input**: JSON files under a root directory, each `{"parsed_plans": [ {...}, ...]}`.
- Plans use `plan_parameters` (e.g. `op_name`, `act_time`, `est_card`, `act_card`, `est_width`) and `children`; runtime = root `act_time` (ms).
- Scans may have `"table": <id>` (mapped to `table_name`); filters from `filter_columns` are converted to `plan_parameters["filter"]` for featurization.

## Usage (from T3 repo root)

Assume `PYTHONPATH` includes the repo root (e.g. `export PYTHONPATH=.` or run from repo).

### Train with one holdout (default: imdb_full as test)

```bash
python -m src.t3_jh.training_jh_holdout
python -m src.t3_jh.training_jh_holdout --data /path/to/parsed_plans --holdout imdb_full --out model_jh_holdout.txt
```

- **Output**: Model saved as `model_jh_holdout.txt` (or `model_jh_holdout_v1.txt`, `_v2.txt`, ... if the path exists).
- **Appends**: `diagnostics_training_jh.txt` (training diagnostics), `holdout_jh.txt` (test summary: min, max, avg, p50, p75, p90 q-error).

### Evaluate a saved model

```bash
python -m src.t3_jh.eval_jh --model model_jh_holdout.txt --data /path/to/parsed_plans
python -m src.t3_jh.eval_jh --model model_jh_holdout.txt --data /path/to/parsed_plans --out results_jh.txt
```

- Appends one line with min/max/avg/p50/p75/p90 to `results_jh.txt` (or `--out` path).

### Full benchmark (all holdouts)

```bash
python -m src.t3_jh.run_full_benchmark_jh
python -m src.t3_jh.run_full_benchmark_jh --data /path/to/parsed_plans --dry-run
```

- For each benchmark folder (accidents, airline, tpc_h, ...), runs `training_jh_holdout` with that folder as holdout.
- Models: `model_jh_holdout_<name>.txt` (versioned if file exists).
- All test summaries appended to `holdout_jh.txt`.

## Metrics

- **q-error** (actual vs predicted runtime).
- Reported: **min**, **max**, **avg**, **p50**, **p75**, **p90** (always appended to the chosen txt file, no overwrite).

## Files

- `jh_util.py`, `jh_operators.py`, `jh_operator_stages.py`, `jh_query_plan.py`, `jh_features.py`, `jh_benchmarked_query.py`, `jh_model.py`: Johannes-style plan/feature/model (no zeroshot, no core T3 plan format).
- `jh_dataloader.py`: Load parsed_plans JSON → normalize → rewrite_children → annotate_op_id → extract_pipeline_infos → QueryPlan → build_pipelines → BenchmarkedQuery.
- `training_jh_holdout.py`: Train with holdout, versioned model name, append diagnostics and holdout summary.
- `eval_jh.py`: Load model, evaluate on JSONs, append min/max/avg/p50/p75/p90.
- `run_full_benchmark_jh.py`: Loop over holdouts and run training (like zeroshot `run_all_holdouts`).

### Debug highest-error queries (feature vectors)

To track down why some test queries get very high q-errors (e.g. holdout good except a few extreme values):

```bash
python -m src.t3_jh.debug_holdout_max_error --holdout tpc_h
python -m src.t3_jh.debug_holdout_max_error --holdout walmart --top 20 --out debug_walmart.md
python -m src.t3_jh.debug_holdout_max_error --holdout tpc_h --zeroshot-model model_zero_holdout_tpc_h.txt
```

- Loads the holdout test set and the holdout model, computes q-error per query, and writes a report for the **top-k** highest-error queries (default `--top 10`).
- For each, the report includes: **actual**, **pred (holdout)**, **q_error**, **source file** and **plan_index**, and **per-pipeline feature vectors** (non-zero entries with feature names) plus scan sizes and actual vs predicted runtime per pipeline.
- With `--zeroshot-model`, loads the same plan via the zeroshot pipeline and adds **zeroshot prediction** and **zeroshot feature vector** for comparison (to see if the issue is feature extraction or model).

Output: `debug_holdout_<holdout>.md` (or `--out`).

Core T3/Umbra files under `src/` are not modified; this package is self-contained under `src/t3_jh/`.
