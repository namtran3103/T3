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

**Usage**

- **Train** (writes `model_pg.txt` by default):
  ```bash
  python -m src.postgres.training
  ```
- **Predict** (reads `model_pg.txt` by default):
  ```bash
  python -m src.postgres.predict_from_pg path/to/15a.json
  python -m src.postgres.predict_all_pg /path/to/pg_explain_job
  ```
- To use another file: `--model other_model.txt` for the predict scripts and `--out other_model.txt` for training.
