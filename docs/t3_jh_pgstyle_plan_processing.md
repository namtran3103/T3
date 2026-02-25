# How t3-Johannes processes a normal PostgreSQL plan

This document describes how the **t3-Johannes** repo (`BA2/t3-Johannes`) processes a **normal PostgreSQL plan**. It refers only to code and concepts in that repo. No reference is made to the T3 repo’s `src/t3_jh`, zeroshot, or `src/postgres`.

**Input:** The pipeline is designed for **PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON)** output. Plans are loaded by **gen_t3_dataset** (in `t3_dataloader.py`) via an external workload loader that returns plans in an **internal form**: each node has **plan_parameters** (e.g. **op_name**, **act_time**, **est_card**, **act_card**) and **children** (list of child nodes), and the root has **plan_runtime_ms**, **run_file_id**, and **sql**. How raw EXPLAIN JSON is turned into that form lives in the workload loader (outside the t3-Johannes repo). This doc starts from the moment the pipeline has such a plan.

One **continuous example** is used: a **Hash Join** with outer **Seq Scan** and inner **Hash(Seq Scan)**.

---

## 1. Normal PG plan and the internal form the pipeline sees

PostgreSQL **EXPLAIN (ANALYZE, FORMAT JSON)** looks like:

```json
[
  {
    "Plan": {
      "Node Type": "Hash Join",
      "Plan Rows": 1000,
      "Actual Rows": 1000,
      "Actual Total Time": 250,
      "Plans": [
        { "Node Type": "Seq Scan", "Actual Rows": 500, "Actual Total Time": 150, "Plans": [] },
        {
          "Node Type": "Hash",
          "Actual Total Time": 50,
          "Plans": [
            { "Node Type": "Seq Scan", "Actual Rows": 100, "Actual Total Time": 50, "Plans": [] }
          ]
        }
      ]
    },
    "Execution Time": 250.5
  }
]
```

The **workload loader** (used by **gen_t3_dataset**; not part of the t3-Johannes repo files) converts this into a plan where each node has **plan_parameters** and **children**. For our example, after that conversion the plan that **gen_t3_dataset** iterates over looks like:

```python
plan = {
    "plan_parameters": {
        "op_name": "Hash Join",
        "est_card": 1000,
        "act_card": 1000,
        "act_time": 250
    },
    "children": [
        {"plan_parameters": {"op_name": "Seq Scan", "act_card": 500, "act_time": 150}, "children": []},
        {
            "plan_parameters": {"op_name": "Hash", "act_card": 100, "act_time": 50},
            "children": [
                {"plan_parameters": {"op_name": "Seq Scan", "act_card": 100, "act_time": 50}, "children": []}
            ]
        }
    ],
    "plan_runtime_ms": 250,
    "run_file_id": "...",
    "sql": "SELECT ..."
}
```

PG order for Hash Join: **children[0]** = outer (probe), **children[1]** = Hash (build). The rest of the pipeline (in t3-Johannes) works only with this internal form.

---

## 2. Entry point: gen_t3_dataset (t3_dataloader.py)

**gen_t3_dataset** takes **workload_runs** (paths to workload files), a **statistics_file**, **model_config**, etc. It calls the external **read_workload_runs** to get **plans** and **db_statistics**. Then for each plan it:

1. Checks **check_plan_runtime_validity(plan, plan["plan_runtime_ms"])** (external); skips if invalid.
2. Calls **assign_additional_plan_info(plan, db_statistics, db_schema_info)** (external) to augment the plan.
3. Calls **extract_query_stats_for_plan(...)** (external).
4. **rewrite_children(plan)** — in **t3_dataloader.py**.
5. **annotate_op_id(plan)** — in **t3_dataloader.py**.
6. **extract_pipeline_infos(plan, pipelines)** — in **t3_dataloader.py**.
7. Builds **QueryPlan(plan, card_type, db_statistics)** — **query_plan.py**.
8. **qp.build_pipelines(pipelines)** — **query_plan.py**.
9. Builds **BenchmarkedQuery(query_plan=qp, total_runtimes=[runtime], ...)** — **benchmarked_query.py**, with **runtime** from **plan["plan_runtime_ms"]** (converted to seconds where needed).

Steps 4–9 are the core of how a single plan is processed inside t3-Johannes. Below we go through them with the same Hash Join example.

---

## 3. rewrite_children (t3_dataloader.py)

**rewrite_children(parsed_plan)** mutates the plan: it **pops** **children** and, depending on **op_name**, sets **left** / **right** or **input** and timing fields.

**For a Hash Join (two children):**

- Code expects **Hash** at index 1 (Postgres usually gives hash at the second position). It takes the Hash node’s single child as the build side.
- **left** = that child (build), **right** = **children[0]** (probe). So **left = build**, **right = probe**.
- **plan_parameters["left_runtime"]** = Hash’s **plan_parameters["act_time"]** (50 ms).
- **plan_parameters["right_runtime"]** = right child’s **act_time** (150 ms).
- **prune_ops** is applied (e.g. **Materialize** is replaced by its child). Then **rewrite_children** is called recursively on **left** and **right**.

After this step the plan has **no** **children** key; it has **left** and **right** (each with **plan_parameters** and possibly their own **left** / **right** / **input**). Unary nodes (Sort, Aggregate, etc.) get **input** and **plan_parameters["input_runtime"]**; **Finalize Aggregate** / **Simple Aggregate** are normalized to **Aggregate** and the input chain is pruned (e.g. through Gather / Partial Aggregate).

---

## 4. annotate_op_id (t3_dataloader.py)

**annotate_op_id(parsed_plan, id=-1)** walks the plan (in order: **input**, then **left**, then **right**) and sets:

- **plan_parameters["op_id"]** = 1-based (1, 2, 3, …),
- **plan_parameters["analyze_plan_id"]** = 0-based (0, 1, 2, …).

For our join: root → op_id 1, analyze_plan_id 0; left (build scan) → 2 and 1; right (probe scan) → 3 and 2. These IDs are used to attach operators to pipelines (**analyze_plan_id**) and to build the operator DAG (**op_id**).

---

## 5. extract_pipeline_infos (t3_dataloader.py)

**extract_pipeline_infos(parsed_plan, pipelines, root=True)** walks the **rewritten** tree (with **left** / **right** / **input**) and fills the list **pipelines**. Each entry is a dict with **operators** (list of **analyze_plan_id**s), **duration** (ms), and then **start** / **stop** set by **add_order_to_pipelines**.

**For a Hash Join:** The build side gets its own pipeline: **left_runtime** (minus child pipeline runtime) is the duration, and **operators** = [join’s analyze_plan_id] + build subtree’s ids (e.g. [0, 1]). The probe side is returned as the “continuing” stream ([0, 2]). So we get one pipeline for the hash (build) and the probe stream is used when building further pipelines up the tree. At the root, a pseudo pipeline is inserted so that the sum of all pipeline **duration**s equals **plan_runtime_ms**; **add_order_to_pipelines** then sets **start** and **stop** on each pipeline so they are ordered in time.

Runtimes come from **plan_parameters** (**act_time**, **left_runtime**, **right_runtime**), so pipeline boundaries and durations are consistent with **Postgres timing**.

---

## 6. QueryPlan and build_pipelines (query_plan.py)

**QueryPlan(plan, card_type, db_statistics)** parses the **rewritten** plan (with **left** / **right** / **input** and **op_id** / **analyze_plan_id**) into an operator DAG. It uses **parse_operator_type** (**operators.py**) with **plan_parameters["op_name"]** and the **pg** name map (e.g. **"Hash Join"** → HashJoin, **"Seq Scan"** → TableScan). Cardinalities come from **plan_parameters** (**est_card** / **act_card** depending on **card_type**); for scans, **db_statistics** (e.g. **table_stats_dict**, **reltuples**) are used for input cardinality when available. Expressions come from **plan_parameters["filter"]** (and join filters if present). Each node becomes an **Operator** (type, op_id, cardinalities, expressions, parent/input links) stored in **query_plan.operators** keyed by **op_id**.

**qp.build_pipelines(pipelines)** (in **query_plan.py**): It builds **operator_dict** from **plan_parameters["analyze_plan_id"]** to **Operator**. For each pipeline dict it collects the corresponding operators, sorts them by “precedes” (data-flow order), and calls **build_pipeline(ops, start, stop)** from **operator_stages.py**, which creates a **Pipeline** of **ExecutionPhase**s (operator + **OperatorStage**: Scan / Build / Probe / PassThrough) and sets **start** / **stop**. **get_operator_stage** (**operator_stages.py**) assigns the stage from operator type and position (e.g. HashJoin: previous op is right → Probe, else Build).

Result: a **QueryPlan** with **operators** and **pipelines** (list of **Pipeline**s, each a list of **ExecutionPhase**s). **fix_union_all** (in **query_plan.py**) adjusts union-all pipelines if needed.

---

## 7. BenchmarkedQuery (benchmarked_query.py)

**BenchmarkedQuery(query_plan=qp, total_runtimes=[runtime], name=None, query_text=sql, query_category=None)** is created with **runtime** = **plan["plan_runtime_ms"]** (in ms; the class stores runtimes in seconds, so conversion is applied where the dataloader passes runtimes). So the **normal PG plan**’s total time becomes the single measured runtime.

**get_total_runtime()** returns the median of **total_runtimes**. **get_analyze_plan_runtime()** uses the query plan’s pipeline **start** / **stop** to compute total span (and converts to seconds). **get_pipeline_runtimes()** distributes total runtime across pipelines using each pipeline’s **start** / **stop** and a correction so the sum equals total runtime. **get_per_tuple_pipeline_runtimes()** = pipeline runtime / pipeline scan cardinality per pipeline. **get_pipeline_runtime_data(feature_mapper)** and **get_per_tuple_pipeline_runtime_data(feature_mapper)** return (feature vector, runtime) per pipeline for training. **get_feature_matrix(feature_mapper)** returns the per-pipeline feature matrix (from **FeatureMapper.get_pipeline_estimation_matrix**).

---

## 8. FeatureMapper and model (features.py, model.py)

**FeatureMapper** (**features.py**): For each pipeline and each **ExecutionPhase**, it builds an estimation vector (cardinalities, tuple sizes, input/output/right percentages, expression counts/selectivities) from the **Operator** and **ExecutionPhase** helpers. **get_pipeline_estimation_matrix(query_plan)** returns one row per pipeline (sum of phase vectors in that pipeline). **get_pipeline_scan_sizes(query_plan)** returns scan cardinality per pipeline.

**Model** (**model.py**): The default T3 per-tuple tree model is trained on **(feature_vector, per_tuple_runtime)** per pipeline (from **get_per_tuple_pipeline_runtime_data**). At inference it predicts per-tuple time per pipeline, multiplies by pipeline scan size, and sums to total runtime. **assemble_x_y** (in **t3_dataloader.py**) builds the (X, Y) arrays from a list of **BenchmarkedQuery** using **get_per_tuple_pipeline_runtime_data** and the **FeatureMapper**.

---

## 9. End-to-end (t3-Johannes repo only)

| Step | Where | What happens |
|------|--------|----------------|
| 0 | (external) | Workload loader turns **normal PG EXPLAIN** into plans with **plan_parameters**, **children**, **plan_runtime_ms**, **run_file_id**, **sql**. |
| 1 | **t3_dataloader.py** | **gen_t3_dataset** gets **plans** and **db_statistics**; for each plan: validity check, **assign_additional_plan_info**, **extract_query_stats_for_plan**. |
| 2 | **t3_dataloader.py** | **rewrite_children(plan)**: **children** → **left** / **right** (Hash Join: left=build, right=probe), **left_runtime** / **right_runtime**; unary → **input**. |
| 3 | **t3_dataloader.py** | **annotate_op_id(plan)**: **op_id** (1-based), **analyze_plan_id** (0-based). |
| 4 | **t3_dataloader.py** | **extract_pipeline_infos(plan, pipelines)**: pipelines from **act_time**, **left_runtime**, **right_runtime**; **add_order_to_pipelines** sets **start** / **stop**. |
| 5 | **query_plan.py** | **QueryPlan(plan, card_type, db_statistics)**: parse **plan_parameters** + **left** / **right** / **input** → **Operator**s; **qp.build_pipelines(pipelines)** → **Pipeline**s with Scan/Build/Probe. |
| 6 | **benchmarked_query.py** | **BenchmarkedQuery(qp, total_runtimes, ...)**: one runtime from **plan_runtime_ms**; exposes feature matrix and pipeline/per-tuple runtimes. |
| 7 | **features.py**, **model.py** | **FeatureMapper** builds per-pipeline feature vectors; **assemble_x_y** and the model use them for training and inference. |

All of the above refers only to the **t3-Johannes** repo (`BA2/t3-Johannes`): **t3_dataloader.py**, **query_plan.py**, **operator_stages.py**, **operators.py**, **features.py**, **benchmarked_query.py**, **model.py**, and the external calls **read_workload_runs**, **check_plan_runtime_validity**, **assign_additional_plan_info**, **extract_query_stats_for_plan** that **gen_t3_dataset** uses to load and augment plans before the steps in this repo.

---

## 10. Comparison with the original T3 core (Umbra)

The **original T3 core** (documented in **docs/umbra_plan_processing.md** in this repo) processes **native Umbra** plans. The **t3-Johannes** pipeline processes **PostgreSQL** plans. Both end up with the same kind of object (QueryPlan with operators and pipelines, BenchmarkedQuery, FeatureMapper, per-tuple model). The main differences are **input format**, **who provides pipelines**, and **how the tree is normalized**.

| Aspect | Original T3 core (Umbra) | t3-Johannes (PostgreSQL) |
|--------|---------------------------|---------------------------|
| **Input** | One **plan wrapper** per file: **plan** (root node tree), **ius**, **analyzePlanPipelines**. Runtimes in the **same file** under **benchmarks** (multiple runs, `executionTime` each). | **PG EXPLAIN (ANALYZE, FORMAT JSON)**. External workload loader converts to internal form: **plan_parameters** + **children** per node, **plan_runtime_ms** on root. One runtime per plan (single run). |
| **Tree shape** | Tree **already** has **left** / **right** / **input**. Node keys: **operator**, **physicalOperator**, **analyzePlanId**, **operatorId**, **cardinality**, **analyzePlanCardinality**, **producedIUs**, **restrictions**, **residuals**. | Tree **starts** with **children** (ordered list). After **rewrite_children**: **children** removed, **left** / **right** or **input** set; **plan_parameters** hold **op_name**, **act_time**, **est_card**, **act_card**, **left_runtime**, **right_runtime**, etc. |
| **Pipelines** | **Provided** with the plan: **analyzePlanPipelines** (list of `{operators, start, stop, duration}`). No extraction; loader/benchmark already produced them. | **Extracted** inside t3-Johannes: **extract_pipeline_infos** walks the rewritten tree and builds pipeline list from **act_time**, **left_runtime**, **right_runtime**; **add_order_to_pipelines** sets **start** / **stop**. |
| **Operator / plan IDs** | **analyzePlanId** and **operatorId** are **already in** the Umbra plan. | **annotate_op_id** **assigns** **op_id** (1-based) and **analyze_plan_id** (0-based) in a single walk. |
| **QueryPlan construction** | Parses from Umbra keys: **operator** + **physicalOperator** → OperatorType; **cardinality** / **analyzePlanCardinality**; **producedIUs** + **ius** for tuple size; **restrictions** / **residuals** for expressions. | Parses from **plan_parameters**: **op_name** → OperatorType via **pg** name map (e.g. "Hash Join" → HashJoin); **est_card** / **act_card**; **db_statistics** for scan input card; **filter** for expressions. |
| **Runtimes** | **benchmarks** list → **total_runtimes** (e.g. one per run). **get_total_runtime()** = median. Pipeline runtimes derived from pipeline **start**/ **stop** and total time. | **plan_runtime_ms** → **total_runtimes** = [runtime] (one value). Same derivation of pipeline runtimes from **start** / **stop** and total. |
| **Downstream** | **build_pipelines(analyzePlanPipelines)** → Pipelines with **ExecutionPhase** + **OperatorStage** (Scan/Build/Probe/PassThrough). **FeatureMapper** → per-pipeline feature matrix + scan sizes. **BenchmarkedQuery** → **get_per_tuple_pipeline_runtime_data**. Per-tuple tree model (LightGBM). | **Same**: **build_pipelines(pipelines)** → same Pipeline/ExecutionPhase/OperatorStage; same FeatureMapper and BenchmarkedQuery API; same per-tuple model and **assemble_x_y** for training. |

**Summary:** The original T3 core assumes the **plan already has** the right tree shape and **pipelines are given**. t3-Johannes assumes a **PG-style plan** (list of children, no pipelines) and **derives** the tree shape (**rewrite_children**) and pipelines (**extract_pipeline_infos**, **add_order_to_pipelines**) from **plan_parameters** and Postgres timing. From **QueryPlan** + pipelines onward, both use the same ideas: operator DAG, pipelines with stages, per-pipeline features, per-tuple runtimes, and the same training/inference model.
