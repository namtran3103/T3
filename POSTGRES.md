# PostgreSQL EXPLAIN → T3 inference (Option A)

Use a PostgreSQL `EXPLAIN (ANALYZE, FORMAT JSON)` plan with T3 for runtime prediction **without training**. The converter in `src/postgres/` turns PG plan JSON into an Umbra-style plan so T3’s pre-trained model can run inference.

---

## Usage

Run from the **T3 project root** (the directory that contains `src/` and, for prediction, `model_pg.txt` from Postgres training). Use the **module name** `src.postgres.predict_from_pg`, not the path to the `.py` file.

```bash
cd /path/to/T3
python -m src.postgres.predict_from_pg /path/to/explain.json
```

Or run the script directly (still from T3 root):

```bash
cd /path/to/T3
python src/postgres/predict_from_pg.py /path/to/explain.json
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| positional `pg_json` | — | Path to PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) output file |
| `--model PATH` | `model_pg.txt` | Path to the pre-trained T3 model file |
| `--db NAME` | `job` | T3 schema/DB name used for table names and sizes (e.g. `job` for JOB) |

**Examples:**

```bash
# Default model and job schema
python -m src.postgres.predict_from_pg queries/job/15a_explain.json

# Custom model and schema
python -m src.postgres.predict_from_pg out/15a.json --model model_pg.txt --db job
```

**Requirements:**

- A pre-trained T3 model (e.g. `model_pg.txt` from `python -m src.postgres.training`). No training is done; inference only.
- PostgreSQL plan from `EXPLAIN (ANALYZE, FORMAT JSON) ...` (array `[{"Plan": {...}}]` or object `{"Plan": {...}}`).
- Table names in the plan (e.g. JOB: `aka_title`, `company_name`, …) must match the T3 schema for `--db`.

---

## Batch script: predict_all_pg

**Script:** `T3/src/postgres/predict_all_pg.py`

- Finds all `*.json` files in the given folder (sorted by name).
- For each file, runs `predict_from_pg_json` and records predicted time, actual time (from JSON), and q-error when actual is present.
- Prints one line per file (unless `--quiet`) and a short summary (counts and q-error min/p50/p90/max).

**How to run** (from the T3 project root):

```bash
cd /path/to/T3
# JOB benchmark (default schema)
python -m src.postgres.predict_all_pg /path/to/pg_explain_job

# TPC-H SF1 plans: use --db tpchSf1 so table names (lineitem, orders, etc.) match
python -m src.postgres.predict_all_pg src/postgres/tpch_sf1/plans --db tpchSf1 --model model_pg.txt
```

**Options:**

| Option | Description |
|--------|-------------|
| `folder` | Directory with PG EXPLAIN JSON files (e.g. `pg_explain_job`) |
| `--model PATH` | T3 model file (default: `model_pg.txt`) |
| `--use-plan-rows` | Use Plan Rows instead of Actual Rows for cardinality |
| `--db NAME` | T3 DB/schema name: `job` (JOB), `tpchSf1` (TPC-H SF1), etc. (default: `job`) |
| `--quiet` | Only print the summary, no per-file lines |

**Example output:**

```
1a.json: pred=0.012345s actual=0.011200s q_err=1.1022
1b.json: pred=0.023456s actual=0.025100s q_err=1.0701
...
Processed 113 files (113 with actual time).
Q-error: min=1.0012 p50=1.4523 p90=3.2100 max=8.5000
```

---

## Limitations

- **Operators:** Only a subset of PG node types is mapped (Seq Scan, Index Scan, Hash Join, Nested Loop, Merge Join, Sort, Aggregate, Limit, Hash, etc.). Others are treated as `map`.
- **Schema / table sizes:** Table names in the plan must exist in the chosen T3 schema (`--db`). If the schema has no table sizes (e.g. fresh cache), missing sizes are filled from scan cardinalities in the plan when possible; otherwise inference may fail or be less accurate.
- **Expressions:** Filter/join expressions are not parsed from PG plan; `restrictions` and `residuals` are left empty, so expression-related features are not used.
- **Accuracy:** The model was trained on Umbra plans and pipeline timings. PG plans are an approximation; expect higher error than on native Umbra plans.

---

## Summary of changes (Postgres model file)

1. **`src/postgres/training.py`**  
   Default output is now `model_pg.txt` (was `model.txt`). Docstring updated to describe this and point to the predict scripts.

2. **`src/postgres/predict_from_pg.py`**  
   Default `model_path` is `model_pg.txt` in `predict_from_pg_json()` and in the `--model` argument. Docstring and error message now refer to `model_pg.txt` and `python -m src.postgres.training`.

3. **`src/postgres/predict_all_pg.py`**  
   Default `--model` is `model_pg.txt`. Example in the docstring updated.

4. **`src/postgres/training_tpch_extended.py`**  
   Trains on TPC-H SF1 **extended** (augmented) plans: 16 examples for training (shuffle seed 42), rest for test. Data from `src/postgres/tpch_sf1/plans/extended/`, DB `tpchSf1`. Writes `model_pg_extended.txt` by default. Use with `predict_from_pg` via `--model model_pg_extended.txt --db tpchSf1` for extended plans.

5. **`src/postgres/training_job_extended.py`**  
   Trains on JOB **extended** (augmented) plans: 80/20 train/test split (seed 42). Data from `src/postgres/pg_explain_job/extended/`, DB `job`. Writes `model_job_extended.txt` by default. Uses extended format (actual_scan_in_card, component_selectivity, ius) when present. Use with `predict_from_pg` via `--model model_job_extended.txt --db job` for JOB extended plans.

**Usage**

- **Train** (writes `model_pg.txt` by default):
  ```bash
  python -m src.postgres.training
  ```
- **Train on TPC-H SF1 extended plans** (16 examples, seed 42, rest for test; writes `model_pg_extended.txt`):
  ```bash
  python -m src.postgres.training_tpch_extended
  ```
  Options: `--data DIR` (default: `src/postgres/tpch_sf1/plans/extended`), `--out PATH` (default: `model_pg_extended.txt`), `--train-n N` (default: 16), `--seed N` (default: 42), `--db NAME` (default: `tpchSf1`), `--no-eval`, `--quiet`.
- **Train on JOB extended plans** (80/20 split, seed 42; writes `model_job_extended.txt`):
  ```bash
  python -m src.postgres.training_job_extended
  ```
  Options: `--data DIR` (default: `src/postgres/pg_explain_job/extended`), `--out PATH` (default: `model_job_extended.txt`), `--seed N` (default: 42), `--train-fraction F` (default: 0.8), `--db NAME` (default: `job`), `--no-eval`, `--quiet`.
- **Predict** (reads `model_pg.txt` by default):
  ```bash
  python -m src.postgres.predict_from_pg path/to/15a.json
  python -m src.postgres.predict_all_pg /path/to/pg_explain_job
  ```
  For extended model and TPC-H SF1 extended plans:
  ```bash
  python -m src.postgres.predict_from_pg src/postgres/tpch_sf1/plans/extended/5.json --model model_pg_extended.txt --db tpchSf1
  ```
  For JOB extended model and JOB extended plans:
  ```bash
  python -m src.postgres.predict_from_pg src/postgres/pg_explain_job/extended/15a.json --model model_job_extended.txt --db job
  ```
- To use another file: `--model other_model.txt` for the predict scripts and `--out other_model.txt` for training.
- **Train on zero-shot parsed plans** (80/20 split, seed 42; writes `model_zero.txt`):
  ```bash
  python -m src.zeroshot.training_zeroshot
  python -m src.zeroshot.training_zeroshot --data /path/to/zero-shot-data/runs/parsed_plans --out model_zero.txt
  ```
  Options: `--data DIR`, `--out PATH` (default: `model_zero.txt`), `--seed N`, `--train-fraction F`, `--no-eval`, `--quiet`.
- **Train on zero-shot with TPC-H holdout** (train on all except `tpc_h`, test on `tpc_h`; writes `model_zero_tpch_holdout.txt`):
  ```bash
  python -m src.zeroshot.training_zeroshot_tpch_holdout
  python -m src.zeroshot.training_zeroshot_tpch_holdout --data /path/to/parsed_plans --out model_zero_tpch_holdout.txt
  ```
  Options: `--data DIR`, `--out PATH` (default: `model_zero_tpch_holdout.txt`), `--holdout NAME` (default: `tpc_h`), `--seed N`, `--no-eval`, `--quiet`.

---

## Zero-shot parsed plans (training only)

Train T3 on **zero-shot** parsed plan JSONs (e.g. from `zero-shot-data/runs/parsed_plans`). Plans are converted to T3 format, split into pipelines (breakers: Hash, Materialize, Sort, Aggregate), and feature vectors are generated. No PostgreSQL EXPLAIN files or schema are required; a minimal in-memory DB is used.

**Script:** `src/zeroshot/training_zeroshot.py`

**Usage** (from T3 project root):

```bash
cd /path/to/T3
# Default data dir and model output model_zero.txt
python -m src.zeroshot.training_zeroshot

# Custom data directory (root containing .json files with parsed_plans)
python -m src.zeroshot.training_zeroshot --data /path/to/zero-shot-data/runs/parsed_plans

# Custom model path (default is model_zero.txt)
python -m src.zeroshot.training_zeroshot --data /path/to/parsed_plans --out model_zero.txt
```

**Options:**

| Option | Default | Description |
|--------|---------|--------------|
| `--data DIR` | `.../zero-shot-data/runs/parsed_plans` | Root directory to search for `*.json` files (recursive) |
| `--out PATH` | `model_zero.txt` | Output path for the trained model |
| `--seed N` | `42` | Random seed for 80/20 train/validation split |
| `--train-fraction F` | `0.8` | Fraction of JSON files used for training |
| `--no-eval` | — | Skip validation set evaluation |
| `--quiet` | — | Less training log output |

**Behavior:**

- Collects all `.json` files under `--data` (each file can contain a `parsed_plans` array with one or more plans).
- Splits **files** with seed 42: 80% train, 20% validation.
- Converts each plan to T3 (pipelines, cardinalities, timings) and trains the per-tuple pipeline model.
- Saves the model to `--out` (default: `model_zero.txt`).
- If not `--no-eval`, runs validation and prints **q-error for each sample** (one line per query: `name pred=...s actual=...s q_error=...`) plus summary (avg, p50, p90, min, max).

**Example output:**

```
...
workload_100k_s1_c8220_0: pred=12.345678s actual=14.291487s q_error=1.1576
accidents/complex_200k_1: pred=0.234567s actual=0.198234s q_error=1.1832
...
Validation set (N queries): q-error avg=1.5234 p50=1.4523 p90=3.2100 min=1.0012 max=8.5000
```

**TPC-H holdout (train on all except TPC-H, test on TPC-H):**

**Script:** `src/zeroshot/training_zeroshot_tpch_holdout.py`

Train on all zero-shot JSONs **except** those under the `tpc_h` directory; use `tpc_h` as the **test set** (leave-one-benchmark-out). Same conversion and training as above; only the split changes.

```bash
python -m src.zeroshot.training_zeroshot_tpch_holdout
python -m src.zeroshot.training_zeroshot_tpch_holdout --data /path/to/parsed_plans --out model_zero_tpch_holdout.txt
```

| Option | Default | Description |
|--------|---------|--------------|
| `--data DIR` | same as above | Root directory for `*.json` files |
| `--out PATH` | `model_zero_tpch_holdout.txt` | Output model path |
| `--holdout NAME` | `tpc_h` | Benchmark folder name to hold out as test set |
| `--seed N` | `42` | Seed for internal train/val split during training |
| `--no-eval` | — | Skip test set evaluation |
| `--quiet` | — | Less training output |

Output includes q-error per test sample and a summary line; results are also written to `holdout.txt` in the project root (first line `holdout=<name>`, then per-sample lines, then the summary).

---

## collect_node_types

**Script:** `src/postgres/collect_node_types.py`

Scans all JSON plan files under `pg_explain_job` and `tpch_sf1` (including subdirs such as `pg_explain_job/extended/` and `tpch_sf1/plans/`, `tpch_sf1/plans/extended/`), recursively collects every `"Node Type"` from the plan trees, and prints a sorted JSON array of unique node types.

**Summary**

- **Input:** All `.json` files in `src/postgres/pg_explain_job` and `src/postgres/tpch_sf1` (recursive).
- **Output:** A JSON list of unique PostgreSQL plan node types (e.g. Aggregate, Seq Scan, Hash Join, Sort, …).
- **Use case:** Inspect which node types appear across your plan corpus (e.g. for operator mapping or coverage checks).

**Usage** (from T3 project root or from `src/postgres`):

```bash
cd /path/to/T3
python src/postgres/collect_node_types.py
```

Print to file:

```bash
python src/postgres/collect_node_types.py > node_types.json
```

**Example output** (node types found in the current plan corpus):

```json
[
  "Aggregate",
  "Bitmap Heap Scan",
  "Bitmap Index Scan",
  "CTE Scan",
  "Gather",
  "Gather Merge",
  "Hash",
  "Hash Join",
  "Incremental Sort",
  "Index Only Scan",
  "Index Scan",
  "Limit",
  "Materialize",
  "Memoize",
  "Merge Join",
  "Nested Loop",
  "Seq Scan",
  "Sort"
]
```
