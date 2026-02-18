# Zero-shot raw data → T3

Pipeline for training T3 on **raw** zero-shot data (`runs/raw`): EXPLAIN (ANALYZE) text plans instead of pre-parsed JSON. Training filters match zero-shot parse_plans (0.1–30 s runtime; no pipeline-span filter). Per-file diagnostics in `diagnostics_training.txt`.

## Summary

- **Input:** Raw zero-shot JSONs under `zero-shot-data/runs/raw`: each file has `query_list`; each query can have `analyze_plans` (PostgreSQL EXPLAIN (ANALYZE) text).
- **Parsing:** Text lines are flattened; only plan-node lines (with `cost=... rows=...` or `actual time=... rows=...`) are parsed. Indentation and `->` define the tree; the root can be the first line without `->`.
- **Operators & cardinalities:** Each line yields `est_*` / `act_*` (cost, rows, width, time). Values are stored **as printed by PostgreSQL** (no multiplication by loops), matching **zero-shot-cost-estimation** (`cross_db_benchmark/benchmark_tools/postgres/plan_operator.py`: `actual_regex` does not capture loops; parsed_plans use raw numbers).
- For scans, "Rows Removed by Filter: N" is used to set `input_cardinality` and `overall_selectivity`.
- **Runtime:** `plan_runtime` is taken from the line **"Execution time: X ms"** when present (same as zero-shot `parse_plan`); otherwise from the root node's `act_time`.
- **Training filters:** match zero-shot **parse_plans**: **0.1 s ≤ runtime ≤ 30 s** (min_runtime=100 ms, max_runtime=30000 ms). No pipeline-span filter (zero-shot has none), so we use at least as many plans as parsed_plans.
- **Tree → T3:** A zeroshot-style plan (`plan_parameters`, `children`, `plan_runtime` in ms) is built and passed to `zeroshot_plan_to_t3()`, so pipeline breakers, PG→T3 operator mapping, and pipeline assignment match the parsed-plans pipeline.

## Modules

| Module | Role |
|--------|------|
| `src.zeroshot.zeroshot_raw_to_t3` | Parse raw EXPLAIN text → tree, map to zeroshot shape, then to T3 (same pipeline breakers / operators as `zeroshot_to_t3`). |
| `src.zeroshot.training_raw_holdout_imdb_full` | Train on all raw JSONs except `imdb_full`; hold out `imdb_full` for test. Writes per-file diagnostics to `diagnostics_training.txt`. |

## Usage

**Training (imdb_full holdout, default raw data dir):**

```bash
# From T3 project root
python -m src.zeroshot.training_raw_holdout_imdb_full
```

**Custom data directory:**

```bash
python -m src.zeroshot.training_raw_holdout_imdb_full --data /path/to/zero-shot-data/runs/raw
```

**Other options:**

- `--out PATH` — Model output path (default: `model_raw_holdout_imdb_full.txt`, or `_v1`, `_v2`, … if it exists).
- `--seed N` — Random seed for train/val split (default: 42).
- `--trees N` — Number of trees (boosting rounds) to train (default: 200).
- `--no-eval` — Skip test set metrics.
- `--quiet` — Less training output.

**Programmatic use of raw → T3 conversion:**

```python
from pathlib import Path
from src.zeroshot.zeroshot_raw_to_t3 import (
    load_raw_json,
    raw_plan_to_t3,
    raw_plan_to_zeroshot,
    convert_raw_file_to_t3,
    collect_all_raw_jsons,
    get_minimal_database,
)
from src.zeroshot.zeroshot_raw_to_t3 import _flatten_plan_lines

# Single file → list of T3 plan dicts
t3_plans = convert_raw_file_to_t3("/path/to/raw/benchmark/workload.json")

# Or manually: raw text lines → T3
data = load_raw_json(path)
for q in data["query_list"]:
    if not q.get("analyze_plans"):
        continue
    lines = _flatten_plan_lines(q["analyze_plans"])
    t3 = raw_plan_to_t3(lines, use_actual_card=True)
    if t3 and t3.get("plan_runtime_seconds"):
        # use t3["plan"], t3["analyzePlanPipelines"], t3["plan_runtime_seconds"]
        ...

# Collect all JSON paths under raw root
paths = collect_all_raw_jsons(Path("/path/to/zero-shot-data/runs/raw"))
```

## Diagnostics

After a training run, `diagnostics_training.txt` is appended with:

- `data_source=raw`, `holdout=imdb_full`, `train_files`, `total_queries_used`
- Per file: `path`, `plans_total`, `added`, `skip_no_runtime`, `skip_out_of_range`, `skip_span_inconsistent`, `skip_exception`, optional `file_error`. (With span filter disabled, `skip_span_inconsistent` is 0.)

This lets you see per-file skip counts to compare with zero-shot parse_plans output.
