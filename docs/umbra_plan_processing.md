# How an Umbra plan is processed by the T3 core

This document explains how a native Umbra plan (wrapper with `plan`, `ius`, `analyzePlanPipelines`) is loaded, parsed, featurized, and used for training or inference. Same explanation style as the plan-structure doc: concrete examples and step-by-step.

---

## 1. Input: Umbra plan structure

**What the T3 core expects:** A single **plan wrapper** dict (e.g. from a benchmark JSON or API) with three top-level pieces:

- **`plan`** – Root operator node (nested tree).
- **`ius`** – List of IU definitions, e.g. `[{"iu": "name", "estimatedSize": size}]`.
- **`analyzePlanPipelines`** – List of pipeline descriptors, each with `operators` (analyzePlanIds), `start`, `stop`, `duration`.

**What “root operator node (nested tree)” means:** **`plan`** is one Python dict. That dict is the **root** of the plan. It does not list all operators; it’s the top of a **tree**: the root has keys **`left`**, **`right`**, or **`input`** whose values are **again dicts** (child nodes). Those child dicts can have their own `left`/`right`/`input`, and so on. So the whole plan is one nested structure you walk by following those keys.

**Minimal example** (HashJoin of two table scans):

```python
wrapper = {
    "plan": {                                    # root operator node
        "operator": "join",
        "physicalOperator": "hashjoin",
        "operatorId": 1,
        "analyzePlanId": 1,
        "cardinality": 1000,
        "analyzePlanCardinality": 1000,
        "producedIUs": [{"estimatedSize": 16}],
        "restrictions": [],
        "residuals": [],
        "left": {                                # child node (build side)
            "operator": "tablescan",
            "operatorId": 2,
            "analyzePlanId": 2,
            "tablename": "A",
            "cardinality": 100,
            "analyzePlanCardinality": 100,
            "inputCardinality": 1000,
            "producedIUs": [{"estimatedSize": 8}],
            "restrictions": [],
            "residuals": []
        },
        "right": {                               # child node (probe side)
            "operator": "tablescan",
            "operatorId": 3,
            "analyzePlanId": 3,
            "tablename": "B",
            "cardinality": 500,
            "analyzePlanCardinality": 500,
            "inputCardinality": 5000,
            "producedIUs": [{"estimatedSize": 8}],
            "restrictions": [],
            "residuals": []
        }
    },
    "ius": [
        {"iu": "default", "estimatedSize": 8}
    ],
    "analyzePlanPipelines": [
        {"operators": [2], "start": 0.0, "stop": 100.0, "duration": 0.0001},
        {"operators": [3], "start": 0.0, "stop": 150.0, "duration": 0.00015},
        {"operators": [1], "start": 100.0, "stop": 250.0, "duration": 0.00015}
    ]
}
```

**How `ius` and `analyzePlanPipelines` relate to the tree:**

- **`ius`** – Catalog: IU name → size (bytes). In the tree, each operator has **`producedIUs`**: either a list of objects `[{"estimatedSize": 8}]` (size inline) or a list of strings like `["default"]` (size looked up in **`ius`**). So **`ius`** is used when computing each operator’s output tuple size.
- **`analyzePlanPipelines`** – Does not duplicate the tree; it **references** the same nodes by **`analyzePlanId`**. Each descriptor says “these operator IDs run together in one pipeline” and gives **start / stop / duration** for that pipeline. So: tree = structure (who is whose child); pipelines = grouping of those same nodes + timing.

| Part | Role |
|------|------|
| **`plan`** | Tree of operators (who is whose child). Each node has `analyzePlanId`, `producedIUs`, etc. |
| **`ius`** | Catalog: IU name → size. Used to resolve **named** IUs in operators’ **`producedIUs`** for tuple size. |
| **`analyzePlanPipelines`** | List of pipeline descriptors: **`analyzePlanId`s** of operators in each pipeline + **start / stop / duration**. |

---

## 2. Loading (training/evaluation path)

**What happens:** One benchmark JSON file is read and turned into a single **BenchmarkedQuery** (one plan + its runtimes and metadata).

**Typical file shape** (conceptually):

```python
benchmark_file = {
    "plan": {                          # the Umbra plan wrapper
        "plan": { ... },                # root operator tree (nested dicts)
        "ius": [{"iu": "default", "estimatedSize": 8}],
        "analyzePlanPipelines": [{"operators": [2], "start": 0, "stop": 100, "duration": 0.0001}, ...],
        "query_text": "SELECT ..."
    },
    "benchmarks": [
        {"executionTime": 0.42},
        {"executionTime": 0.39},
        {"executionTime": 0.41}
    ]
}
```

**Two parts in the same file:** The benchmark JSON has two separate top-level keys that are used for different things:

| Key | Contents | Used for |
|-----|----------|----------|
| **`plan`** | Umbra plan wrapper (`plan`, `ius`, `analyzePlanPipelines`) + `query_text` | Building the **QueryPlan** (structure + pipelines). |
| **`benchmarks`** | List of **run records**, each with **`executionTime`** (seconds) | The **measured runtimes** for that query (same query executed multiple times). |

So the **plan** describes *what* was executed; **benchmarks** holds *how long* each run took. They live in the same file so one file = one logical query with one plan and several timing samples.

**How runtimes get attached:** The code does not “add” execution time into the plan. It reads both parts from the file and passes the runtimes into **BenchmarkedQuery** as a separate field:

1. **Load JSON** from `file` → `benchmark_json` (contains both `plan` and `benchmarks`).
2. **Build QueryPlan** from the plan part only: `benchmark_json["plan"]` (or the inner `plan`/`ius`/`analyzePlanPipelines`) → **QueryPlan** + **build_pipelines(...)**. The plan tree and pipelines do not contain any execution time.
3. **Collect runtimes from the other key:**  
   `runtimes = [b["executionTime"] for b in benchmark_json["benchmarks"]]`  
   So for each element in the **`benchmarks`** list, we take its **`executionTime`** and build a list, e.g. `[0.42, 0.39, 0.41]` (seconds).
4. **Build BenchmarkedQuery:**  
   `BenchmarkedQuery(plan, runtimes, file.name, query_text, category)`  
   The second argument is that list of runtimes; it is stored as **`total_runtimes`** on the **BenchmarkedQuery**. So the “benchmarks / executionTime section” is exactly that list: one number per run, same query, multiple runs.

Later, **`get_total_runtime()`** on that **BenchmarkedQuery** returns the **median** of **`total_runtimes`** (one representative time for training or evaluation). So: **one file → one QueryPlan (from `plan`) + one list of runtimes (from `benchmarks`) → one BenchmarkedQuery** that holds both the plan and the measured runtimes.

---

## 3. QueryPlan construction (`src/query_plan.py`)

**What happens:** The plan wrapper (tree + ius + pipelines) is turned into an in-memory **operator DAG** and **pipelines with stages**.

**Input:** A dict **`plan`** that has at least **`"plan"`** (root node) and **`"ius"`** (list of IU definitions).

**Step 1 – Store root and IUs**

- `self.json_plan = plan["plan"]` → the single root dict (the top of the tree).
- `self.ius = {iu["iu"]: iu["estimatedSize"] for iu in plan["ius"]}` → e.g. `{"default": 8}`.

**Step 2 – Walk the tree and build `Operator`s**

`_parse_operator(self.json_plan, [])` is called with the root. For **each node**:

- **Type:** `parse_operator_type(op)` looks at `op["operator"]` (and for joins `op["physicalOperator"]`) and returns an **OperatorType** (e.g. `TableScan`, `HashJoin`, `IndexNLJoin`, `GroupBy`, `Sort`). Example: `operator: "join"`, `physicalOperator: "hashjoin"` → `OperatorType.HashJoin`.
- **Cardinalities:** From the node (and children): output (`cardinality` / `analyzePlanCardinality`), input, and for joins right input → `_get_output_cardinality`, `_get_input_cardinality`, `_get_right_cardinality`.
- **Tuple size:** From **`producedIUs`** and **`self.ius`** (as in the IU example: either inline `estimatedSize` or lookup by name).
- **Expressions:** **`restrictions`** and **`residuals`** are turned into counts/selectivities (e.g. compare, like, in, between, or) via `_parse_expressions` → `_featurize_expression` / `_get_expression_selectivity`.

Then an **Operator** is created (type, op_id, cardinalities, tuple size, expressions, parent/input links) and stored in **`self.operators[op_id]`**. The code then recurses:

- Join → `_parse_operator(op["left"], ...)` and `_parse_operator(op["right"], ...)`.
- Unary (Sort, GroupBy, Select, …) → `_parse_operator(op["input"], ...)`.

So the **nested tree of dicts** becomes a **flat dict of Operator objects** keyed by **`operatorId`**, with parent/child links.

**Step 3 – Build pipelines and stages**

`plan.build_pipelines(pipelines)` is called with **`analyzePlanPipelines`**: a list of `{"operators": [id, ...], "start", "stop", "duration"}`.

- **Lookup:** `operator_dict = {op.json["analyzePlanId"]: op for op in self.operators.values()}` → map id → Operator.
- **Per pipeline:** For each descriptor, collect the Operators by id, **sort by “precedes”** (so order in the pipeline is data-flow order), then call **`build_pipeline(ops, start, stop)`** in **`operator_stages.py`**.
- **Stage:** For each operator in that pipeline, **`get_operator_stage(op_index, op, pipeline_ops)`** decides **OperatorStage**:
  - TableScan, InlineTable, PipelineBreakerScan → **Scan**.
  - Select, Map → **PassThrough**.
  - Temp, CsvWriter, FileOutput → **Build**.
  - HashJoin: not first in pipeline; if previous op is the **right** child → **Probe**, else (previous is **left**) → **Build**.
  - IndexNLJoin: similar (Probe vs Build by left/right).
  - GroupBy/Sort: first or last in pipeline → **Scan** or **Build** depending on position.

So each pipeline becomes a **Pipeline** object: a list of **ExecutionPhase**s (operator + stage + pipeline + fraction). **`fix_union_all`** then adjusts union-all pipelines (shared tail, fractions).

**Result:** One **QueryPlan** with:

- **`operators`**: id → **Operator** (the DAG).
- **`pipelines`**: list of **Pipeline**s, each a list of **ExecutionPhase**s (operator + stage).

So: **one wrapper → one QueryPlan (operator DAG + pipelines with stages)**.

### Concrete example (§3): HashJoin(Scan A, Scan B)

Use the same wrapper as in §1: root = HashJoin, **left** = TableScan A (id 2), **right** = TableScan B (id 3). Pipelines: build A → `[2]`, build B → `[3]`, probe join → `[1]`.

- **Step 1:** `json_plan` = root dict; `ius` = `{"default": 8}`.
- **Step 2 – build Operators:**  
  - Root node: `operator: "join"`, `physicalOperator: "hashjoin"` → **OperatorType.HashJoin**. Cardinalities: output 1000, input (left) 100, right 500. Tuple size 16. → **Operator(op_id=1, type=HashJoin, output_card=1000, input_card=100, right_card=500, ...)**. Recurse to left and right.  
  - Left node (Scan A): → **Operator(op_id=2, type=TableScan, output_card=100, input_card=1000, ...)**.  
  - Right node (Scan B): → **Operator(op_id=3, type=TableScan, output_card=500, input_card=5000, ...)**.  
  So **`query_plan.operators`** = `{1: join_op, 2: scanA_op, 3: scanB_op}`.
- **Step 3 – build pipelines:**  
  - Descriptor `{"operators": [2], "start": 0, "stop": 100, ...}` → one operator (id 2). Order by “precedes” → `[scanA_op]`. **get_operator_stage**(TableScan, …) → **Scan**. So **Pipeline 0** = `[ ExecutionPhase(scanA_op, Scan, pipeline0) ]`.  
  - Descriptor `{"operators": [3], ...}` → **Pipeline 1** = `[ ExecutionPhase(scanB_op, Scan, pipeline1) ]`.  
  - Descriptor `{"operators": [1], ...}` → **Pipeline 2** = `[ ExecutionPhase(join_op, Probe, pipeline2) ]`.  

So after §3 we have: **QueryPlan** with 3 operators and 3 pipelines; each pipeline has one phase (one operator + one stage).

---

## 4. Feature extraction (`src/features.py`)

**What happens:** That **QueryPlan** is turned into **one fixed-size feature vector per pipeline** (and optionally scan sizes).

**Per operator (phase):** For each **ExecutionPhase** in each pipeline, **`get_estimation_vector(phase)`** builds one vector:

- The **feature set** is fixed: it’s the list of **QualifiedFeature**s (operator type × stage × feature dim). Example: for **HashJoin_Probe** you might have dims like input_card, right_percentage, out_percentage, and for **TableScan_Scan**: scan (in_card, in_size), out_percentage, expressions (like_percentage, compare_percentage, …), empty_output.
- **Values** come from the phase: cardinalities, tuple sizes, **input/output/right percentage** (from `phase.get_input_percentage()` etc., i.e. share of pipeline scan cardinality), and from **phase.operator.expressions** (counts and selectivities).

So one **ExecutionPhase** → one vector (mostly zeros; non-zero only for the dimensions that apply to that operator type and stage).

**Per pipeline:** **`get_pipeline_estimation_matrix(query_plan)`**:

- For each pipeline: start with an all-zero vector, then **add** the estimation vectors of every phase in that pipeline → **one vector per pipeline**.
- So you get a matrix with **one row per pipeline**.

**Scan sizes:** **`get_pipeline_scan_sizes(query_plan)`** returns an array: for each pipeline, the “scan cardinality” (e.g. first operator’s input or output for GroupBy/Sort/Temp).

So: **QueryPlan → per-pipeline feature matrix + per-pipeline scan sizes**.

### Concrete example (§4): same HashJoin plan

We have 3 pipelines, each with one phase: **Pipeline 0** = Scan A, **Pipeline 1** = Scan B, **Pipeline 2** = Join (Probe).

- **Pipeline 0 – TableScan_Scan (Scan A):**  
  Feature dims for TableScan_Scan: **scan** (in_card, in_size), **out** (out_percentage), **expressions**, **empty_output**.  
  Values: `in_card = 1000` (scan’s input cardinality), `in_size = 8`, `out_percentage = 100/1000 = 0.1` (output rows / pipeline scan cardinality; pipeline scan card = first op’s input = 1000). No filters → expression slots 0. So we get a vector **v0** (one row, many columns; only the TableScan_Scan slots non-zero).
- **Pipeline 1 – TableScan_Scan (Scan B):**  
  Same shape: `in_card = 5000`, `in_size = 8`, `out_percentage = 500/5000 = 0.1` → vector **v1**.
- **Pipeline 2 – HashJoin_Probe:**  
  Feature dims for HashJoin_Probe: **input_card**, **right** (right_percentage), **out** (out_percentage).  
  Pipeline scan cardinality for this pipeline = first op’s input = join’s left input = 100. So: `input_card = 100`, `right_percentage = 500/100 = 5`, `out_percentage = 1000/100 = 10` → vector **v2**.

**`get_pipeline_estimation_matrix(query_plan)`** returns a matrix with 3 rows: row 0 = **v0**, row 1 = **v1**, row 2 = **v2** (each pipeline has only one phase, so no summing within pipeline).

**`get_pipeline_scan_sizes(query_plan)`** returns `[1000, 5000, 100]`: for pipeline 0 the scan card is Scan A’s input (1000), for pipeline 1 it’s Scan B’s input (5000), for pipeline 2 it’s the join’s left input (100).

---

## 5. BenchmarkedQuery and runtime data

**What it is:** **BenchmarkedQuery** holds the **QueryPlan** plus **measured runtimes** and metadata (name, query_text, category).

**Feature matrix:** **`get_feature_matrix(feature_mapper)`**:

- First time: calls **`feature_mapper.get_pipeline_estimation_matrix(self.query_plan)`** and caches the result.
- Returns a matrix: **one row per pipeline** (same as in §4).

**Pipeline runtimes (for training):** **`get_pipeline_runtimes()`**:

- Uses **total runtime** (e.g. median of `total_runtimes`) and **analyze plan duration** (from pipeline start/stop in the plan).
- Splits total time across pipelines proportionally to **`(p.stop - p.start)`** so that the sum of pipeline times equals total time (with overlap handling and a correction factor if needed).
- Returns a list: **one runtime per pipeline** (in seconds).

**Per-tuple runtimes (for per-tuple model):** **`get_per_tuple_pipeline_runtimes()`**:

- For each pipeline: `runtime / pipeline.get_pipeline_scan_cardinality()` (or just runtime if scan cardinality is 0).
- So: **one “time per tuple” per pipeline**.

**Per-tuple training data:** **`get_per_tuple_pipeline_runtime_data(feature_mapper)`**:

- **Features:** `get_feature_matrix(feature_mapper)` → one row per pipeline.
- **Targets:** `get_per_tuple_pipeline_runtimes()` → one value per pipeline.
- Returns a list of **(feature_vector, per_tuple_runtime)** pairs, one per pipeline.

So: **BenchmarkedQuery** = QueryPlan + runtimes; it exposes **feature matrix** and **pipeline / per-tuple runtimes** for training or inference.

### Concrete example (§5): same HashJoin plan with runtimes

We build **BenchmarkedQuery(plan, runtimes=[0.42, 0.39, 0.41], name="q1.json", query_text="...", category)**. So **`total_runtimes`** = `[0.42, 0.39, 0.41]` (seconds, three runs of the same query).

- **`get_total_runtime()`** = median(total_runtimes) = **0.41** s. That is the single “measured time” for this query (e.g. for training targets or evaluation).
- **`get_feature_matrix(feature_mapper)`** returns the same 3-row matrix as in §4: row 0 = v0, row 1 = v1, row 2 = v2. It is cached on the **BenchmarkedQuery**.
- **`get_analyze_plan_runtime()`**: from the plan’s pipeline start/stop (e.g. 0 µs to 250 µs) → (250 − 0) / 1e6 = **0.00025** s. So “analyze plan duration” = 0.00025 s.
- **`get_pipeline_runtimes()`**: We want one runtime per pipeline that **sums to total_time = 0.41**. The code uses the ratio of each pipeline’s duration in the plan to the total analyze-plan duration, then scales by total_time and applies a correction so the sum is exactly 0.41. Example: if pipeline 0 had duration 100 µs, pipeline 1 had 50 µs, pipeline 2 had 100 µs (total 250 µs), then before correction: 0.41×(100/250) ≈ 0.164, 0.41×(50/250) ≈ 0.082, 0.41×(100/250) ≈ 0.164; sum = 0.41. So **pipeline runtimes** = e.g. **[0.164, 0.082, 0.164]** s.
- **`get_per_tuple_pipeline_runtimes()`**: For each pipeline, runtime / scan cardinality. With scan sizes **[1000, 5000, 100]** we get: 0.164/1000 = **0.000164**, 0.082/5000 = **0.0000164**, 0.164/100 = **0.00164** (seconds per tuple).
- **`get_per_tuple_pipeline_runtime_data(feature_mapper)`** returns **[(v0, 0.000164), (v1, 0.0000164), (v2, 0.00164)]**: one (feature vector, per-tuple runtime) pair per pipeline, used as (x, y) for training the per-tuple model.

---

## 6. Model (training)

**What happens:** Many **BenchmarkedQuery**s are turned into **one PerTupleTreeModel** (LightGBM).

**Data:** For each **BenchmarkedQuery**, **`get_per_tuple_pipeline_runtime_data(feature_mapper)`** gives a list of **(x, y)** where:

- **x** = one pipeline’s feature vector (from §4).
- **y** = that pipeline’s **per-tuple runtime** (runtime / scan cardinality).

All these **(x, y)** pairs from all queries are **stacked** into big arrays **X** and **y**.

**Training:** **y** is transformed (e.g. clamped and **-log(y)**), then a **LightGBM** model is trained (e.g. MAPE, 200 rounds) to predict this per-tuple target from **x**. So the model learns: **“for a pipeline with this feature vector, what is the (transformed) time per tuple?”**

**At prediction time:** Pipeline time = **predicted per-tuple time × pipeline scan size** (see §7). So: **many Umbra plans → many BenchmarkedQueries → (feature matrix, per-tuple runtimes) → one PerTupleTreeModel**.

---

## 7. Model (inference)

**What happens:** For **one** BenchmarkedQuery (with its QueryPlan already built from an Umbra plan), the model returns a **total predicted runtime**.

**Steps:**

1. **Feature matrix:** **`query.get_feature_matrix(feature_mapper)`** → one row per pipeline (same as §4).
2. **Scan sizes:** **`feature_mapper.get_pipeline_scan_sizes(query.query_plan)`** → one scan cardinality per pipeline.
3. **Predict:** **`predict(x, scan_sizes)`**:
   - The tree predicts a value per pipeline row (in the transformed space).
   - **`pred = np.exp(-pred)`** (inverse of the -log used in training).
   - **`pred = pred * scan_sizes`** (per-tuple time × number of tuples → pipeline time).
   - Mask and clamp to non-negative.
4. **Total:** **`estimate_runtime(query)`** = **sum of these per-pipeline times**.

So: **Umbra plan → QueryPlan → BenchmarkedQuery → feature matrix + scan sizes → model.predict → sum = total runtime**.

---

## End-to-end flow (summary)

| Step | What you have | What happens |
|------|----------------|--------------|
| 1 | One Umbra plan wrapper (**plan**, **ius**, **analyzePlanPipelines**) | Loaded (e.g. from file) and optionally wrapped in BenchmarkedQuery with runtimes. |
| 2 | That wrapper | **QueryPlan**: parse tree → Operators; **build_pipelines** → Pipelines with Scan/Build/Probe/PassThrough stages. |
| 3 | QueryPlan | **FeatureMapper**: per pipeline, sum phase vectors → **one feature vector per pipeline** (+ scan sizes). |
| 4 | QueryPlan + runtimes | **BenchmarkedQuery**: holds plan; exposes **feature matrix** and **pipeline / per-tuple runtimes**. |
| 5 (train) | Many BenchmarkedQueries | **(feature vector, per-tuple runtime)** per pipeline, stacked → train LightGBM → **PerTupleTreeModel**. |
| 5 (infer) | One BenchmarkedQuery | **Feature matrix + scan sizes** → model predicts per-pipeline time → **sum = total runtime**. |

So: the core only ever sees the **wrapper** (plan tree + ius + analyzePlanPipelines). It parses it into **QueryPlan**, **FeatureMapper** turns that into **features and scan sizes**, and the **model** uses those for training (per-tuple targets) or prediction (per-pipeline then total time).
