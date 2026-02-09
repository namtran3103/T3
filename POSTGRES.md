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
- **Train on zero-shot with imdb_full holdout** (train on all except `imdb_full`, test on `imdb_full`; writes `model_zero_holdout_imdb_full.txt` or `_v1`, `_v2`, … if it exists; appends training diagnostics to `diagnostics_training.txt` with timestamp and holdout):
  ```bash
  python -m src.zeroshot.training_zeroshot_imdb_full_holdout
  python -m src.zeroshot.training_zeroshot_imdb_full_holdout --data /path/to/parsed_plans
  ```
  Options: `--data DIR`, `--out PATH` (default: `model_zero_holdout_imdb_full.txt`, or next free `_vN` if file exists), `--seed N`, `--no-eval`, `--quiet`. See **imdb_full holdout** section below for diagnostics output.
- **Train on zero-shot DeepDB-augmented with holdout** (data from `runs/deepdb_augmented/`; writes `model_zero_holdout_<name>_augmented.txt`; appends to `holdout_augmented.txt`):
  ```bash
  python -m src.zeroshot.training_zeroshot_tpch_holdout_augmented
  python -m src.zeroshot.run_all_holdouts_augmented
  ```
  Options: `--data DIR` (default: `.../runs/deepdb_augmented`), `--out PATH`, `--holdout NAME`, `--dry-run` (run_all only).
- **Few-shot finetune zero-shot holdout models** (loads `model_zero_holdout_<name>.txt`, finetunes on up to 50 queries per holdout evenly over JSONs, seed 42; writes `model_zero_holdout_<name>_fewshot.txt`; appends to `holdout_fewshot.txt`):
  ```bash
  python -m src.zeroshot.training_zeroshot_holdout_fewshot
  python -m src.zeroshot.run_all_holdouts_fewshot
  ```
  Options: `--data DIR`, `--holdout NAME`, `--num-queries N` (default: 50), `--dry-run` (run_all only).

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

Output includes q-error per test sample (to stdout) and a summary line; only the **summary line** is appended to `holdout.txt` in the project root (e.g. `Test set (tpc_h, N queries): q-error avg=... p50=... p90=... min=... max=...`).

**imdb_full holdout (train on all except imdb_full, test on imdb_full; versioned output; training diagnostics):**

**Script:** `src/zeroshot/training_zeroshot_imdb_full_holdout.py`

Same as TPC-H holdout but with **imdb_full** as the holdout and default output **`model_zero_holdout_imdb_full.txt`**. If that file already exists, the script saves to **`model_zero_holdout_imdb_full_v1.txt`**, then `_v2`, etc. (next free number). No overwrite of existing models. Each run **appends training diagnostics** to **`diagnostics_training.txt`** (timestamp, holdout name, per-file used/skipped counts, totals) so you can see whether all plans were used or some were skipped (e.g. no runtime, conversion error).

**Usage** (from T3 project root):

```bash
# Default data dir and versioned model output
python -m src.zeroshot.training_zeroshot_imdb_full_holdout

# Custom parsed-plans root
python -m src.zeroshot.training_zeroshot_imdb_full_holdout --data /path/to/parsed_plans
```

| Option | Default | Description |
|--------|---------|--------------|
| `--data DIR` | `.../zero-shot-data/runs/parsed_plans` | Root directory for `*.json` files |
| `--out PATH` | `model_zero_holdout_imdb_full.txt` (or next free `_vN`) | Output model path; if path exists, `_v1`, `_v2`, … used |
| `--seed N` | `42` | Seed for internal train/val split during training |
| `--no-eval` | — | Skip test set evaluation |
| `--quiet` | — | Less training output |

**Output:** Test summary is appended to `holdout.txt` (same line schema as TPC-H holdout). **Training diagnostics** are appended to **`diagnostics_training.txt`** in the project root: each block has `timestamp` (UTC), `holdout=imdb_full`, `train_files`, `total_queries_used`, one line per train file (`plans`, `added`, `skip_no_runtime`, `skip_exception`, optional `file_error`, and `[ok]` or `[skipped_some]`), then totals. Use this file to see if any plans were skipped during training.

**Run all holdouts:** `src/zeroshot/run_all_holdouts.py` runs the holdout script once per benchmark (hardcoded list from `parsed_plans`). For each run: `--holdout <name>`, `--out model_zero_holdout_<name>.txt`. It clears `holdout.txt` at start; each run appends to it, so the file ends up with all holdouts' results in order.

```bash
python -m src.zeroshot.run_all_holdouts
python -m src.zeroshot.run_all_holdouts --data /path/to/parsed_plans
```
Options: `--data DIR` (default: `.../zero-shot-data/runs/parsed_plans`), `--dry-run` (print commands only).

**Few-shot finetuning of holdout models:** Load a zero-shot holdout model (`model_zero_holdout_<name>.txt`), continue training on up to N queries (default 50) from that holdout, evenly distributed over its JSON files (seed 42), then save `model_zero_holdout_<name>_fewshot.txt` and append test summary to **`holdout_fewshot.txt`**.

- **Single holdout** — `src/zeroshot/training_zeroshot_holdout_fewshot.py`:
  ```bash
  python -m src.zeroshot.training_zeroshot_holdout_fewshot
  python -m src.zeroshot.training_zeroshot_holdout_fewshot --holdout tpc_h --num-queries 50
  ```
  Options: `--data DIR`, `--holdout NAME` (default: `tpc_h`), `--num-queries N` (default: 50), `--num-boost-round N` (default: 30), `--seed N` (default: 42), `--model-in PATH`, `--out PATH` (default: `model_zero_holdout_<holdout>_fewshot.txt`), `--no-eval`, `--quiet`.
- **All holdouts** — `src/zeroshot/run_all_holdouts_fewshot.py`: clears `holdout_fewshot.txt`, then for each benchmark runs the few-shot script; models saved as `model_zero_holdout_<name>_fewshot.txt`, results appended to `holdout_fewshot.txt`.
  ```bash
  python -m src.zeroshot.run_all_holdouts_fewshot
  python -m src.zeroshot.run_all_holdouts_fewshot --data /path/to/parsed_plans --num-queries 100
  ```
  Options: `--data DIR`, `--num-queries N` (default: 50), `--dry-run`.

**Summary (few-shot):** Input: zero-shot holdout models and `parsed_plans` (non-augmented). Queries for finetuning are sampled evenly across the holdout’s JSON files (seed 42), up to `--num-queries`. Output: `model_zero_holdout_<name>_fewshot.txt` per holdout; test-set lines in `holdout_fewshot.txt` (same line schema as `holdout.txt`). **Visualize:** `python holdout_to_md.py --input holdout_fewshot.txt` → `holdout_fewshot_results.md` and `holdout_fewshot_p50_bars.png`.

---

## Zero-shot DeepDB-augmented plans (training only)

Train T3 on **DeepDB-augmented** zero-shot runs (`runs/deepdb_augmented/`): same schema as `parsed_plans` but with DeepDB SPN cardinality estimates per node (`dd_est_card`, `dd_est_children_card`). Conversion uses `src/zeroshot/augmented_zeroshot_to_t3.py`, which prefers `dd_est_card` over `est_card` when present.

**Scripts:**

- **`src/zeroshot/augmented_zeroshot_to_t3.py`** — Converts DeepDB-augmented JSON to T3 format (same pipeline/timing logic as `zeroshot_to_t3`, cardinality from `dd_est_card` / `dd_est_children_card` when available).
- **`src/zeroshot/training_zeroshot_tpch_holdout_augmented.py`** — Same holdout training as `training_zeroshot_tpch_holdout` but reads from `runs/deepdb_augmented/` and uses the augmented converter; writes models named `*_augmented.txt` and appends results to **`holdout_augmented.txt`** (same line schema as `holdout.txt`).
- **`src/zeroshot/run_all_holdouts_augmented.py`** — Runs holdout training for every benchmark on DeepDB-augmented data; models: `model_zero_holdout_<name>_augmented.txt`; clears then appends to `holdout_augmented.txt`.

**Usage** (from T3 project root):

```bash
# Single holdout (default: tpc_h)
python -m src.zeroshot.training_zeroshot_tpch_holdout_augmented
python -m src.zeroshot.training_zeroshot_tpch_holdout_augmented --data /path/to/deepdb_augmented --holdout imdb --out model_zero_holdout_imdb_augmented.txt

# Run all holdouts (hardcoded list under deepdb_augmented)
python -m src.zeroshot.run_all_holdouts_augmented
python -m src.zeroshot.run_all_holdouts_augmented --data /path/to/deepdb_augmented
```

| Option | Default | Description |
|--------|---------|-------------|
| `--data DIR` | `.../zero-shot-data/runs/deepdb_augmented` | Root directory containing benchmark subdirs with augmented JSONs |
| `--out PATH` | `model_zero_tpch_holdout_augmented.txt` | Output model path (per-holdout: `model_zero_holdout_<name>_augmented.txt`) |
| `--holdout NAME` | `tpc_h` | Benchmark folder to hold out as test set |
| `--dry-run` | — | (run_all_holdouts_augmented only) Print commands, do not run |

**Output:** One line per holdout appended to `holdout_augmented.txt`, same schema as `holdout.txt`:  
`Test set (name, N queries): q-error avg=... p50=... p90=... min=... max=...`

**Visualize augmented results:** Use `holdout_to_md.py` with `--input holdout_augmented.txt` to generate `holdout_augmented_results.md` and `holdout_augmented_p50_bars.png`:

```bash
python holdout_to_md.py --input holdout_augmented.txt
```

**Summary**

- **Input:** `runs/deepdb_augmented/` (parsed plans + DeepDB cardinalities).
- **Conversion:** `augmented_zeroshot_to_t3` uses `dd_est_card` / `dd_est_children_card` when present.
- **Models:** `model_zero_holdout_<name>_augmented.txt`.
- **Results file:** `holdout_augmented.txt`; report: `python holdout_to_md.py --input holdout_augmented.txt`.

**Visualize holdout results:** `holdout_to_md.py` (in the project root) reads `holdout.txt` and writes `holdout_results.md` with a markdown table of q-error per dataset (queries, avg, p50, p90, min, max) and an **Averages (over datasets)** section with the mean of avg, p50, p90, min, and max across all holdouts.

**Usage** (from the T3 project root, after `holdout.txt` has been filled e.g. by `run_all_holdouts`):

```bash
cd /path/to/T3
python holdout_to_md.py
```

**Summary**

- **Input:** `holdout.txt` (one line per holdout: `Test set (name, N queries): q-error avg=... p50=... p90=... min=... max=...`).
- **Output:** `holdout_results.md` — title, dataset count and total queries; a table of all datasets with queries and q-error metrics; and a final table with averaged **avg**, **p50**, **p90**, **min**, **max** over datasets.

**Evaluate JOB full only:** `src/zeroshot/eval_imdb_full.py` evaluates **only** the `job_full_c8220.json` file in `imdb_full` with the model trained with imdb_full held out (`model_zero_holdout_imdb_full.txt`). Prints and writes all per-sample results plus summary to `job_zero_t3_results.txt`.

```bash
python -m src.zeroshot.eval_imdb_full
python -m src.zeroshot.eval_imdb_full --data /path/to/parsed_plans/imdb_full --out job_zero_t3_results.txt
```
Options: `--data DIR` (directory containing `job_full_c8220.json`; default: `.../parsed_plans/imdb_full`), `--model PATH` (default: `model_zero_holdout_imdb_full.txt`), `--out PATH` (default: `job_zero_t3_results.txt`).

**Evaluate JOB-light only:** `src/zeroshot/eval_imdb_job_light.py` evaluates only the four JOB-light JSONs in `imdb` (`job-light_c8220.json`, `job-light_repl_1_c8220.json`, `job-light_repl_2_c8220.json`, `job-light_repl_3_c8220.json`) with the **imdb** holdout model (`model_zero_holdout_imdb.txt`). Prints and writes all per-sample results plus summary to `job_light_zero_t3_results.txt`.

```bash
python -m src.zeroshot.eval_imdb_job_light
python -m src.zeroshot.eval_imdb_job_light --data /path/to/parsed_plans/imdb --out job_light_zero_t3_results.txt
```
Options: `--data DIR` (directory containing the four JOB-light JSONs; default: `.../parsed_plans/imdb`), `--model PATH` (default: `model_zero_holdout_imdb.txt`), `--out PATH` (default: `job_light_zero_t3_results.txt`).

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
