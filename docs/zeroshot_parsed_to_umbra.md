# Zero-shot parsed plans → Umbra/T3 entrypoint

This document explains what **`src/zeroshot`** does for **parsed plans only**: from the zero-shot parsed format to the Umbra/T3 entrypoint. Parsed plans = JSON with a **`parsed_plans`** array (e.g. under `zero-shot-data/runs/parsed_plans`). No raw EXPLAIN text.

One **continuous example** is used throughout: a single parsed plan that is a **Hash Join** with outer **Seq Scan** and inner **Hash(Seq Scan)**. After conversion it becomes the same kind of Umbra wrapper as in [umbra_plan_processing.md](umbra_plan_processing.md).

---

## Where parsed plans come from

Under **`zero-shot-data/runs/parsed_plans`** you have one JSON file per benchmark run (e.g. `imdb/job-light_c8220.json`, `tpc_h/workload_100k_s1_c8220.json`). Each file has this shape:

```json
{
  "parsed_plans": [
    { "plan_parameters": { ... }, "children": [ ... ], "plan_runtime": 562.803 },
    { "plan_parameters": { ... }, "children": [ ... ], "plan_runtime": 328.994 },
    ...
  ]
}
```

- **`parsed_plans`**: array of **parsed plan** objects (one per query or per analyze plan in that run).
- Each element is one plan tree: **`plan_parameters`** (op name, cardinalities, timing, filters, etc.) and **`children`** (list of child nodes, same structure). Optionally **`plan_runtime`** (total for that plan, in **milliseconds**).

So the zeroshot code does **not** run a PG query or parse raw text; it starts from these **already-parsed** JSON trees.

---

## Running example: one parsed plan

We follow **one** parsed plan from the array. It is a simple Hash Join: outer = Seq Scan (probe side), inner = Hash(Seq Scan) (build side). In zero-shot, Hash Join’s **children** are `[outer, inner]`; if the second child is a **Hash** node, the converter uses that Hash’s child as the build subtree.

**Minimal zero-shot parsed plan (our example):**

```python
zs_plan = {
    "plan_parameters": {
        "op_name": "Hash Join",
        "est_card": 1000,
        "act_card": 1000,
        "est_width": 16,
        "act_startup_cost": 0,
        "act_time": 250
    },
    "children": [
        {
            "plan_parameters": {
                "op_name": "Seq Scan",
                "est_card": 500,
                "act_card": 500,
                "est_width": 8,
                "act_startup_cost": 0,
                "act_time": 150
            },
            "children": []
        },
        {
            "plan_parameters": {"op_name": "Hash", "est_card": 100, "act_card": 100, "est_width": 8, "act_startup_cost": 0, "act_time": 50},
            "children": [
                {
                    "plan_parameters": {
                        "op_name": "Seq Scan",
                        "est_card": 100,
                        "act_card": 100,
                        "est_width": 8,
                        "act_startup_cost": 0,
                        "act_time": 50
                    },
                    "children": []
                }
            ]
        }
    ],
    "plan_runtime": 250
}
```

So: root = **Hash Join**; **children[0]** = outer **Seq Scan** (500 rows, 150 ms); **children[1]** = **Hash** whose child is inner **Seq Scan** (100 rows, 50 ms). **plan_runtime** = 250 ms (total for this plan).

---

## Step 1: Import-time patch

When **`zeroshot_to_t3`** is imported, it runs **`apply_zeroshot_operator_stages_patch()`** from **`operator_stages_patch.py`**. That patches **`get_operator_stage`** in **`src/operator_stages`** so that for **IndexNLJoin** the “previous operator” in a pipeline can be anywhere in the join’s left or right subtree, not only the direct child. Zeroshot’s tree shape (e.g. after mapping Nested Loop + pass-through ops) can put extra nodes between the join and its children; the patch avoids asserts and keeps stage assignment (Scan/Build/Probe) correct when T3 builds pipelines later. For our **Hash Join** example the patch does not change behaviour; it matters for Nested Loop–style plans.

---

## Step 2: Load JSON and take one parsed plan

The caller (e.g. **`training_zeroshot.load_benchmarked_queries_from_zeroshot`** or an eval script) does:

- **`data = load_zeroshot_json(path)`** → full JSON dict (e.g. `{"parsed_plans": [...]}`).
- **`plans = data.get("parsed_plans", [])`**.
- For each **`zs_plan`** in **`plans`**, it runs the conversion and then the T3 entrypoint. Our example is that **one** `zs_plan` (the Hash Join above).

---

## Step 3: Convert one parsed plan to T3/Umbra — `zeroshot_plan_to_t3(zs_plan)`

This is the main conversion in **`zeroshot_to_t3.py`**. It returns a single dict in **Umbra entry format**: **`{ "plan", "ius", "analyzePlanPipelines", optional "plan_runtime_seconds" }`**.

### 3.1 Tree conversion: `_convert_node(zs_node, next_id, use_actual_card)`

The root **`zs_plan`** is converted recursively. **`next_id[0]`** starts at 1 and is incremented for each new node (→ **operatorId** and **analyzePlanId**).

- **Root (Hash Join):**  
  **op_name** "Hash Join" → **operator** `"join"`, **physicalOperator** `"hashjoin"`.  
  Cardinality from **plan_parameters**: **act_card** 1000 (if use_actual) → **cardinality** and **analyzePlanCardinality** 1000.  
  **est_width** 16 → **producedIUs** `[{ "estimatedSize": 16 }]`.  
  Zero-shot order: **children[0]** = outer (probe), **children[1]** = Hash(inner). The code takes the **Hash**’s single child as the build subtree. So: **left** = convert(inner Seq Scan), **right** = convert(outer Seq Scan). That matches Umbra/operator_stages: **left = build**, **right = probe**.  
  → Umbra node **id 1**: join, hashjoin, card 1000, left = (converted inner), right = (converted outer).

- **Inner Seq Scan (under Hash):**  
  **op_name** "Seq Scan" → **operator** `"tablescan"`, **tablename** `"unknown"`, **inputCardinality** 1. **act_card** 100, **est_width** 8 → cardinality 100, producedIUs size 8. No **filter_columns** in our example → **restrictions** stay empty.  
  → Umbra node **id 2**: tablescan, card 100.

- **Outer Seq Scan:**  
  Same idea: **op_name** "Seq Scan" → tablescan, **act_card** 500.  
  → Umbra node **id 3**: tablescan, card 500.

So after **Step 3.1** we have an **Umbra tree**: root = join (id 1), **left** = scan id 2 (100 rows), **right** = scan id 3 (500 rows). No **filter_columns** in this example; when present, **`_convert_filter_columns_to_tree`** turns zero-shot **operator** / **children** into T3 **expression** / **input** / **direction** trees and appends them to **restrictions** on scan nodes.

### 3.2 Pipeline assignment: `_assign_pipelines(root_umbra, ...)`

The **converted** Umbra tree is walked to assign each **analyzePlanId** to a **pipeline id**. Pipeline breakers (start of a new pipeline) are: **Sort**, **GroupBy**, and **Temp** with **pgMaterialize** (Materialize). For a **Hash Join** (per paper figure): the **build** side (left) is in the current pipeline; the **join** and **probe** side (right) are in the next pipeline together.

- Left (build, id 2) → pipeline **0** (build side only).  
- Join (id 1) and Right (probe, id 3) → pipeline **1** (probe pipeline).

So **pipeline_by_id** = {2: 0, 1: 1, 3: 1}. Inverted: **pipeline 0** = [2], **pipeline 1** = [1, 3]. Order within each pipeline is by “precedes” (data flow): pipeline 0 = [scan 2], pipeline 1 = [scan 3, join 1].

### 3.3 Timing: `_fill_times_zeroshot(zs_plan, root_umbra, times_by_id)`

For each node, **act_startup_cost** and **act_time** from **plan_parameters** are converted to microseconds and stored keyed by **analyzePlanId**. For Hash Join, the code matches the inner (under Hash) to **left** and the outer to **right**. So we get e.g. **times_by_id** = {1: (0, 250_000), 2: (0, 50_000), 3: (0, 150_000)} µs.

### 3.4 Build `analyzePlanPipelines` and wrapper

For each pipeline id (0, 1): **operators** = list of analyzePlanIds in that pipeline; **start** / **stop** = min/max of the times in **times_by_id** for those ids (µs); **duration** = (stop − start) / 1e6 (seconds). **ius** = e.g. `[{ "iu": "default", "estimatedSize": 8 }]`. **plan_runtime** 250 ms → **plan_runtime_seconds** = 0.25.

**Result for our example:**

```python
converted = {
    "plan": root_umbra,   # join id 1, left=scan 2, right=scan 3
    "ius": [{"iu": "default", "estimatedSize": 8}],
    "analyzePlanPipelines": [
        {"operators": [2], "start": 0, "stop": 50_000, "duration": 0.05},
        {"operators": [3, 1], "start": 0, "stop": 250_000, "duration": 0.25}
    ],
    "plan_runtime_seconds": 0.25
}
```

This is exactly the **Umbra entry format** the T3 core expects (see [umbra_plan_processing.md](umbra_plan_processing.md)).

---

## Step 4: Reach the Umbra/T3 entrypoint

Callers then feed **`converted`** into the same path as a native Umbra plan:

1. **`db = get_minimal_database()`** → minimal T3 **Database** (e.g. schema with table `"unknown"`) so **QueryPlan** can run without a real schema.
2. **`plan = QueryPlan(converted, db, predicted_cardinalities=False)`** → T3 parses **converted["plan"]** and **converted["ius"]** into operators and IUs (same as native Umbra).
3. **`plan.build_pipelines(converted["analyzePlanPipelines"])`** → T3 builds pipelines and assigns Scan/Build/Probe (using the patched **get_operator_stage** when needed).
4. **`BenchmarkedQuery(plan, [runtime_sec], name, "", QueryCategory.fixed)`** → runtime from **converted["plan_runtime_seconds"]** (e.g. 0.25). If **plan_runtime_seconds** is missing or ≤ 0, this plan is usually skipped.

From here on it is **standard T3**: the same **QueryPlan**, **FeatureMapper**, and **Model** as for native Umbra plans (training: per-tuple pipeline data; inference: feature matrix + scan sizes → predicted runtime).

---

## End-to-end (parsed plans only)

| Step | What happens |
|------|----------------|
| 1 | **Import** → operator_stages patch (for IndexNLJoin). |
| 2 | **Load** JSON from e.g. `parsed_plans/imdb/job-light_c8220.json` → **parsed_plans** array. |
| 3 | For **one** `zs_plan`: **zeroshot_plan_to_t3(zs_plan)** → **_convert_node** (plan_parameters + children → Umbra tree), **_assign_pipelines** (breakers + join build/probe), **_fill_times_zeroshot** (start/stop per id), then build **analyzePlanPipelines** and **{ plan, ius, analyzePlanPipelines, plan_runtime_seconds? }**. |
| 4 | **T3 entry:** **QueryPlan(converted, db, ...)** → **plan.build_pipelines(converted["analyzePlanPipelines"])** → **BenchmarkedQuery(..., [plan_runtime_seconds], ...)**. |

So for **parsed plans only**, **`src/zeroshot`** takes the zero-shot **parsed** JSON (the kind produced under **`zero-shot-data/runs/parsed_plans`**) and, via **`zeroshot_plan_to_t3`**, turns it into the **same Umbra-style wrapper** the T3 core uses. The only extra step before T3 is that conversion and the minimal database; no PG query is run and no raw EXPLAIN text is parsed in this path.
