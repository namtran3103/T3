# T3 Project Structure and File Reference

This document summarizes the paper, the project layout, and what every file does.

---

## Paper Summary (t3.pdf)

**T3: Accurate and Fast Performance Prediction for Relational Database Systems With Compiled Decision Trees** (SIGMOD’25, Rieger & Neumann, TUM)

- **Goal:** Predict query execution time without running the query; focus on **accuracy**, **low latency**, and **zero-shot** (works on new DB instances without retraining).
- **Idea:** **Tuple Time Tree (T3)** — a compiled decision tree model that:
  1. **Pipeline-based representation:** Splits the physical plan into pipelines; predicts time per pipeline and sums.
  2. **Tuple-centric targets:** Predicts “time per tuple” for each pipeline, then multiplies by input cardinality.
  3. **Compilation:** LightGBM trees compiled to native code via **lleaves** for ~4μs inference.
- **Target system:** Umbra; training on 21 instances (TPC-H, TPC-DS, JOB, airline, accident, baseball, etc.); test on TPC-DS (sf1/10/100). Training uses ~13k queries; test ~2k+ TPC-DS queries.

---

## Project Structure (High Level)

```
T3-Max/
└── T3/
    ├── main.py                 # Master script: data, train, eval, figures
    ├── Readme.md               # Usage, Docker, citation
    ├── pyproject.toml          # Python deps (LightGBM, lleaves, DuckDB, etc.)
    ├── requirements.txt        # Pip lockfile
    ├── Dockerfile              # Docker image for full reproduction
    ├── .gitignore
    ├── model.txt               # Serialized LightGBM T3 model (200 trees, 110 features)
    ├── benchmark_setup/        # DB schemas, load scripts, data-load SQL
    ├── queries/                # Fixed benchmark queries (TPC-H, TPC-DS, JOB)
    ├── dp/                     # C++ join-order microbenchmark (DPsize + T3 vs Cout)
    └── src/                    # Core Python: plans, features, training, evaluation, figures
```

---

## What Every File Does

### Root / Config

| File | Purpose |
|------|---------|
| **main.py** | Entry point. Downloads or uses existing benchmark data, trains two models (exact vs estimated cardinalities), builds `QueryEstimationCache` for evaluation, sets figure output, then runs all figure scripts (latency/accuracy, error histograms, tables, ablation, cardinality degradation, etc.). With `-c` runs C++ join-order experiment; with `-b` reproduces full DB benchmarks; with `-j` benchmarks JOB with DP plans; with `-r` resets intermediate files. |
| **Readme.md** | Install (Docker / native / uv), how to reproduce figures and optional benchmarks, citation. |
| **pyproject.toml** | Project metadata and dependencies (e.g. lightgbm, lleaves, duckdb, matplotlib, numpy, requests, sqlparse). |
| **requirements.txt** | Pip-installable dependency list. |
| **Dockerfile** | Image to run full pipeline (including DB and C++ parts) on x86_64 Linux. |
| **.gitignore** | Ignores `data/`, `venv/`, `downloaded_data/`, `figure_output/`, `benchmark_setup/db`, `dp/bin/`, `dp/LightGBM/`, webserver binary, etc. |
| **model.txt** | Exported LightGBM model (v4, MAPE, 110 feature names, 200 trees). Used for evaluation and for compiling with lleaves in the C++ experiment. |

---

### benchmark_setup/

| File | Purpose |
|------|---------|
| **scripts/load_data.sh** | Bash script: creates `benchmark_setup/db/all.db`, then for each of the 21 instances runs the DB tool with the corresponding schema and load-query file (e.g. `01-tpchSf1-schema.sql` + `01-tpchSf1-load.sql`), filling one combined DB used for benchmarking. |
| **queries/data_load_generation.py** | Reads schema SQL files and generates COPY-from-CSV statements for non-TPC instances (airline, ssb, accident, etc.); can write load SQL files (parts commented out). |
| **queries/01-tpchSf1-load.sql** … **01-tpchSf100-load.sql** | COPY commands for TPC-H sf1/sf10/sf100 (e.g. `copy tpchSf100.lineitem from '...' delimiter '|'`). |
| **queries/02-tpcdsSf1-load.sql** … **02-tpcdsSf100-load.sql** | Same for TPC-DS. |
| **queries/03-job-load.sql** … **21-fhnk-load.sql** | Load SQL for JOB, airline, ssb, walmart, financial, basketball, accident, movielens, baseball, hepatitis, tournament, credit, employee, consumer, geneea, genome, carcinogenesis, seznam, fhnk (paths/options may refer to CSVs or external data). |
| **schemata/01-tpchSf1-schema.sql** … **01-tpchSf100-schema.sql** | CREATE SCHEMA + tables for TPC-H sf1/10/100. |
| **schemata/02-tpcdsSf1-schema.sql** … **02-tpcdsSf100-schema.sql** | Same for TPC-DS. |
| **schemata/03-job-schema.sql** … **21-fhnk-schema.sql** | Schemas for the other 19 instances (JOB, airline, accident, baseball, etc.). |
| **schemata/input.sql** | Raw schema input used as source for conversion. |
| **schemata/schema_conversion.py** | Converts a generic schema (e.g. `input.sql`) into a prefixed schema file (e.g. `21-fhnk-schema.sql`) by adding a schema prefix to table names. |

---

### queries/

| Path | Purpose |
|------|---------|
| **tpch/** | TPC-H benchmark queries (1.sql–22.sql; some with `.postgres` variants). |
| **tpcds/** | TPC-DS benchmark queries (1.sql–99.sql; some with `.postgres`). |
| **job/** | Join Order Benchmark queries (1a–33c, etc.), used for join-order microbenchmark and Zero Shot comparison. |

These are the “fixed” benchmark queries; the rest of the workload is **generated** by `src/query_generation/` and run via the benchmark runner.

---

### dp/ (Join-Order Microbenchmark)

| File | Purpose |
|------|---------|
| **DP.cpp** | C++ implementation of DPsize join ordering using T3 (via lleaves-compiled model) vs Cout cost. Reads cardinality oracle and plan format; outputs optimal join orders and timings. Measures T3 inference latency and scaling. |
| **BenchmarkDPResult.py** | After C++ has produced `model_plans.sql` and `cout_plans.sql`, runs the DB benchmarker on JOB with those plans, compares execution times (Cout vs T3 vs native DB), writes a small LaTeX table (e.g. `tbl_join_order_execution_times`). |
| **dp_to_sql.py** | Reads C++ output (join order as parenthesized plan strings), maps to JOB relation names/aliases, and generates executable SQL (with correct join order) for `model_plans.sql` and `cout_plans.sql`; also produces `query_names.txt`. |
| **compile.sh** | Builds the C++ binary (`dp/bin/dp_experiment` or similar) with CMake in `dp/bin/`. |
| **compile_lightgbm.sh** | Builds LightGBM C API static library in `dp/LightGBM/bin/` (used if C++ side links against LightGBM; main T3 path uses lleaves). |
| **lleaves_header.hpp** | C++ header to call the lleaves-compiled predict function (feature layout must match Python `FeatureMapper`). |
| **latencyScaling.json** | (Generated) Latency vs number of pipelines for compiled/interpreter runs, used by `latency_scaling_figure`. |
| **CMakeLists.txt** | CMake config for the C++ join-order binary. |

---

### src/ — Core Python

#### Entry / Orchestration

| File | Purpose |
|------|---------|
| **__init__.py** | Package marker. |

#### Data & DB

| File | Purpose |
|------|---------|
| **database.py** | `Database` and schema cache: loads `Schema` (tables, columns, sizes, stats), talks to the Umbra HTTP server for table counts, column sizes, and column statistics; serializes schema to JSON cache. |
| **database_manager.py** | Singleton registry of all 21 `Database` instances (by name); `get_train_databases()` (excludes TPC-DS), `get_test_databases()` (TPC-DS only), `get_all_databases()`. |
| **schemata.py** | Parses schema SQL: `Schema`, `Table`, `Column`, `Type`; discovers join columns; loads/saves schema JSON; provides `load_schema(path)`. |

#### Query Plans & Operators

| File | Purpose |
|------|---------|
| **query_plan.py** | Parses Umbra JSON physical plan into `QueryPlan`: builds operator tree (`Operator`), resolves cardinalities (estimated vs analyzed), builds pipelines from `analyzePlanPipelines`; one feature matrix per pipeline. |
| **operators.py** | `OperatorType` enum (TableScan, HashJoin, GroupBy, Sort, …), `Operator` (type, cardinalities, tuple size, expressions), `Expressions` (counts/selectivities for like, compare, in, between, or, starts_with, join_filter, false); `parse_operator_type()` from plan JSON. |
| **operator_stages.py** | `OperatorStage` (Scan, Build, Probe, PassThrough), `ExecutionPhase` (operator + stage + pipeline + fraction), `Pipeline` (operators, scan cardinality, timing); `build_pipeline()` from plan; per-stage percentage/cardinality helpers for feature computation. |

#### Features & Model

| File | Purpose |
|------|---------|
| **features.py** | `Feature` / `FeatureDim` enums; `QualifiedFeature` maps (OperatorType, OperatorStage) → list of dimensions; `FeatureMapper`: builds a single 110-dim vector per pipeline (counts + percentages + cards + sizes + expression features) from a `QueryPlan`; used by training and inference. |
| **model.py** | `TreeModel`: one prediction per pipeline, sum = query time; `PerTupleTreeModel`: predicts time per tuple, then multiplies by pipeline scan cardinality (paper’s main model); `FlatTreeModel`: one vector per query (sum of pipeline vectors), single prediction; all wrap a LightGBM `Booster` and use `FeatureMapper`. |
| **optimizer.py** | `QueryCategory` enum (fixed, select, join_agg, …); `BenchmarkedQuery` (plan, runtimes, name, SQL, category); `get_feature_matrix()`, `get_pipeline_runtimes()` from plan + runtimes; training target construction (median runtime, per-tuple time, log-transform for MAPE). |

#### Training

| File | Purpose |
|------|---------|
| **train.py** | `optimize_all(predicted_cardinalities)`: loads benchmarks for train DBs (via `DataCollector`), optionally excludes categories, then calls `optimize_per_tuple_tree_model(benchmarks)` to train the per-tuple LightGBM model; returns the `Model` used in evaluation. |

#### Data Collection & Benchmarks

| File | Purpose |
|------|---------|
| **data_collection.py** | `DataCollector`: reads benchmark JSONs from `data/`, gets median runtime, query text, category; reads analyzed plan and builds `BenchmarkedQuery`; groups by query name; selects representative run per query; `collect_benchmarks(db_list, predicted_cardinalities, ...)` for training/eval. |
| **benchmark.py** | `Benchmarker`: HTTP client to Umbra server; `planVerboseAnalyze` for plan + cardinalities; runs query multiple times for timings; runs per-DB benchmark (fixed + generated queries), writes JSONs under `data/`; uses query generators from `query_generation/`. |
| **benchmark_runner.py** | Top-level `benchmark()`: updates schema (table/column sizes and stats) for all DBs via server, then runs `Benchmarker` for each DB with fixed iteration count and number of random queries per category. |
| **benchmark_setup.py** | Downloads from T3 Backblaze bucket (`download_t3_file`); generates TPC-H/TPC-DS data with DuckDB (`gen_tpch`, `gen_tpcds`) and exports to CSV/tbl; `download_csvs()`, `create_tpc_data()`, `load_csvs_to_db()` for full DB setup. |

#### Evaluation & Metrics

| File | Purpose |
|------|---------|
| **evaluation.py** | `QueryEstimationCache`: for a given model and cardinality mode, runs `model.estimate_runtime(b)` and `estimate_pipeline_runtime(b)` on all collected benchmarks and stores `EstimatedQuery`; helpers for error statistics and formatting. |
| **metrics.py** | `q_error(real, estimate)` (max(real/est, est/real)) and `abs_error`; used by evaluation and figures. |

#### Server & Utils

| File | Purpose |
|------|---------|
| **server.py** | Starts/stops the Umbra `webserver` process (e.g. `./webserver benchmark_setup/db/all.db`) for local benchmarking. |
| **util.py** | `AutoNumber` enum base; `fifo_cache`; `get_lines`; `rm_rec` for cleanup. |

---

### src/query_generation/

| File | Purpose |
|------|---------|
| **query_structures.py** | `BindingTable`, `BindingColumn`, `IntermediateResult`; helpers to sample random columns for projections/group-by. |
| **expressions.py** | Random filter expressions: compare, like, in, between, or; uses column stats for constants; used by selections and table scans. |
| **selections.py** | `Selection`, `SelectionQuery`, `SelectionFactory`; `sample_complex_selection_query` (single-table + filters + project); used for “select” and “complex_select” query groups. |
| **aggregations.py** | `Aggregation`, `GroupBy`, aggregation functions; `sample_group_by_query` (single table, optional filters, GROUP BY, aggregates); used for aggregate and pseudo-aggregate groups. |
| **join_graph.py** | `Join`, `JoinGraph`; finds joinable columns from schema; samples join graphs; `generate_join_query` (multi-table join, optional selections); used for join-only and select+join groups. |
| **join_agg.py** | `join_aggregations_to_sql`, `generate_join_agg_query`, `generate_join_simple_agg_query` (join + GROUP BY ± group columns); used for join_agg / select_join_agg and simple-agg groups. |
| **window_function.py** | `WindowFunctionFactory`, window aggregates; generates “window” category queries. |
| **__init__.py** | Package marker. |

Together these implement the paper’s “16 query structures × 40 queries per DB” random workload.

---

### src/figures/

| File | Purpose |
|------|---------|
| **infra.py** | Plot style, colors, figure path/format/LaTeX flag; `write_latex_file()` for small tables (e.g. join-order execution times). |
| **latency_accuracy.py** | Figure 1–style: latency vs accuracy (e.g. T3 vs Zero Shot / Stage / AutoWLM); uses `QueryEstimationCache`. |
| **latency_scaling.py** | Figure 5–style: prediction latency vs number of pipelines (compiled vs interpreted ST/MT); reads `dp/latencyScaling*.json`. |
| **query_runtimes.py** | Benchmark variance / run-time distribution (e.g. Figure 6). |
| **accuracy_table.py** | Writes main accuracy table (q-error by train/test/TPC-DS/scale) to file/LaTeX. |
| **detailed_acc_table.py** | More detailed accuracy breakdown. |
| **error_histogram.py** | Q-error distribution (e.g. Figure 7). |
| **error_by_query_type.py** | Q-error by query type (e.g. Figure 8). |
| **per_database_acc.py** | Leave-one-DB-out training and per-DB accuracy (e.g. Figure 9). |
| **est_card_acc.py** | Accuracy with exact vs estimated cardinalities (train/eval combinations); Figure 11–style. |
| **acc_comparison.py** | Comparison to AutoWLM/Stage (literature numbers). |
| **acc_comparison_zero_shot.py** | Comparison to Zero Shot on JOB (e.g. Figure 10). |
| **per_tuple.py** | Ablation: per-tuple vs per-pipeline vs per-query (e.g. Figure 13). |
| **clean_benchmarks.py** | Ablation: number of benchmark runs (e.g. Figure 14). |
| **cardinality_degradation.py** | Artificially degrade cardinalities and plot q-error (e.g. Figure 12). |
| **pipeline_predictions.py** | Pipeline-level prediction visualization (e.g. Figure 2–style). |
| **__init__.py** | Package marker. |

Each figure script can be run standalone (e.g. `python src/figures/latency_accuracy.py`) or is invoked from `main.py` in order.

---

## Data Flow (Summary)

1. **Setup:** `benchmark_setup/` schemas + load scripts + `load_data.sh` → one DB. Optionally `benchmark_setup.py` downloads CSVs, generates TPC data, loads DB.
2. **Benchmarks:** `benchmark_runner.benchmark()` → `Benchmarker` runs fixed + generated queries via Umbra HTTP, saves JSONs in `data/`.
3. **Training:** `DataCollector.collect_benchmarks()` reads those JSONs → `BenchmarkedQuery`; `train.optimize_all()` builds per-tuple targets and trains LightGBM → saved/used as `model.txt` and in-memory `Model`.
4. **Evaluation:** `QueryEstimationCache(model, use_estimated_card)` runs model on all test benchmarks; figure scripts consume this and write PDFs/tables.
5. **C++ path:** `main.py -c` compiles model with lleaves, runs `dp/bin` binary to produce join orders and latency stats; `dp_to_sql` turns them into SQL; optionally `BenchmarkDPResult.py` benchmarks those plans.

This matches the paper’s pipeline-based, tuple-centric T3 design and the repo’s layout; every file above contributes to either data setup, training, evaluation, or figure reproduction.
