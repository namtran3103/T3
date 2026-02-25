# What src/t3_jh adds to t3-Johannes

This document explains what **`src/t3_jh`** (in this T3 repo) adds on top of the **t3-Johannes** pipeline. Same style as [umbra_plan_processing.md](umbra_plan_processing.md), [zeroshot_parsed_to_umbra.md](zeroshot_parsed_to_umbra.md), and [t3_jh_pgstyle_plan_processing.md](t3_jh_pgstyle_plan_processing.md): one simple example per step, explained simply.

**Context:** The **t3-Johannes** repo (`BA2/t3-Johannes`) is built for **normal PostgreSQL plans**: it expects plans that come from an external workload loader (e.g. **read_workload_runs**) with **plan_parameters**, **children**, **plan_runtime_ms**, and often **db_statistics** (real table sizes). The T3 repo’s **`src/t3_jh`** reuses the same pipeline idea (rewrite_children, annotate_op_id, extract_pipeline_infos, QueryPlan, build_pipelines, BenchmarkedQuery, features, model) but **feeds it from zero-shot parsed plans** instead: JSON files under e.g. **`zero-shot-data/runs/parsed_plans`** with a **`parsed_plans`** array. Those parsed plans have **no** external db_statistics and **no** table-level row counts — only **output** cardinalities per operator. This doc walks through what t3_jh does differently, step by step.

One **continuous example** is used: a **Hash Join** with outer **Seq Scan** (500 rows) and inner **Hash(Seq Scan)** (100 rows), total **plan_runtime** 250 ms — the same shape as in the other docs.

---

## 1. Input: parsed_plans instead of workload-run plans

**t3-Johannes** gets plans from **read_workload_runs**: each plan already has **plan_parameters**, **children**, **plan_runtime_ms**, and the loader provides **db_statistics** (e.g. **table_stats_dict** with **reltuples** per table).

**t3_jh** instead loads **parsed_plans** JSON (e.g. from **`zero-shot-data/runs/parsed_plans`**):

```json
{
  "parsed_plans": [
    {
      "plan_parameters": {
        "op_name": "Hash Join",
        "est_card": 1000,
        "act_card": 1000,
        "act_time": 250
      },
      "children": [
        { "plan_parameters": { "op_name": "Seq Scan", "est_card": 500, "act_card": 500, "act_time": 150 }, "children": [] },
        {
          "plan_parameters": { "op_name": "Hash", "act_card": 100, "act_time": 50 },
          "children": [
            { "plan_parameters": { "op_name": "Seq Scan", "est_card": 100, "act_card": 100, "act_time": 50 }, "children": [] }
          ]
        }
      ]
    }
  ]
}
```

So: **one file** can contain **many** plans; each plan has **plan_parameters** (op_name, est_card, act_card, act_time, etc.) and **children** (list). There is **no** separate **db_statistics** file and **no** table size (reltuples) in the JSON — only **output** cardinalities (est_card, act_card) per node.

---

## 2. Entry point: load_parsed_plans_from_json (jh_dataloader.py)

**t3-Johannes** uses **gen_t3_dataset** in **t3_dataloader.py**, which calls **read_workload_runs** and then for each plan runs **assign_additional_plan_info**, **rewrite_children**, **annotate_op_id**, **extract_pipeline_infos**, **QueryPlan**, **build_pipelines**, **BenchmarkedQuery**.

**t3_jh** uses **load_parsed_plans_from_json**: it takes a list of JSON paths (parsed_plans files), and for **each plan** in **parsed_plans** it:

1. Deep-copies the plan and sets **plan_runtime_ms** = root **act_time**, **sql** = "", **run_file_id** = file stem.
2. **\_normalize_plan_node(plan, run_file_id, table_stats_global)** — see §3.
3. Skips if root **act_time** ≤ 0 or **\_check_plan_runtime_validity** fails.
4. **rewrite_children(plan)** — same logic as t3-Johannes (Hash at index 1 → left = build, right = probe; unary → input).
5. **annotate_op_id(plan)** — same as t3-Johannes (op_id 1-based, analyze_plan_id 0-based).
6. **extract_pipeline_infos(plan, pipelines)** — same pipeline extraction.
7. Builds **db_statistics** from **table_stats_global** (see §4).
8. **QueryPlan(plan, card_type, db_statistics)** → **qp.build_pipelines(pipelines)** → **BenchmarkedQuery(...)** with **total_runtimes = [root_act_time / 1000.0]**.

So the **pipeline steps** (rewrite_children, annotate_op_id, extract_pipeline_infos, QueryPlan, build_pipelines, BenchmarkedQuery) are the same as t3-Johannes; the differences are **where the plan comes from**, **how db_statistics is built**, and **how scan input cardinality is set** — all below.

---

## 3. Normalize plan node: table_name and filter (jh_dataloader.py)

**\_normalize_plan_node(node, run_file_id, table_stats)** walks the plan and:

- For **Seq Scan** / **Parallel Seq Scan**: reads **plan_parameters["table"]** (table id). If present, sets **plan_parameters["table_name"]** = **"t{id}"** (e.g. **t0**); otherwise **"unknown"**. Then it **fills table_stats**:  
  **table_stats[table_name] = max(1, act_card or est_card)**.  
  So the “table stats” we collect are **not** real table sizes; they are the **output** cardinality of the scan (rows out). Parsed_plans do not contain input (table) cardinality.
- If **plan_parameters** has **filter_columns**, converts them to **plan_parameters["filter"]** in the JH expression format (operator + children) via **\_filter_columns_to_jh_expression**.

**Example:** Our outer Seq Scan has **act_card** 500, no **table** id → **table_name** = **"unknown"**, **table_stats["unknown"]** = 500. Inner Seq Scan has **act_card** 100, **table_name** = **"unknown"** (or e.g. **t5** if **table** was 5), **table_stats[...]** = 100. So we only ever store **output** card as the value for that table name.

---

## 4. db_statistics from table_stats_global (jh_dataloader.py)

**t3-Johannes** gets **db_statistics** from the workload loader (e.g. **read_workload_runs**), including **table_stats_dict** with **reltuples** (real table row count) per table.

**t3_jh** has **no** external statistics. For each file it keeps a **table_stats_global** dict, updated by **\_normalize_plan_node** for every plan in that file. Then **before** building **QueryPlan** for a plan it sets:

```python
db_statistics["table_stats_dict"] = {
    t: {"relname": t, "reltuples": v} for t, v in table_stats_global.items()
}
if not db_statistics["table_stats_dict"]:
    db_statistics["table_stats_dict"] = {"unknown": {"relname": "unknown", "reltuples": 1}}
```

So **reltuples** for each table is exactly the value we stored in **table_stats_global** — i.e. the **output** cardinality of a scan that touched that table (or 1 if we never saw that table and fall back to **unknown**). So for parsed_plans, **db_statistics** does **not** contain true table sizes; it contains **output-card-as-proxy** (or 1).

---

## 5. How leaf input cardinality is set for scans (jh_query_plan.py)

In the T3/Umbra model, a **TableScan** has an **input cardinality** (rows in the table) and an **output cardinality** (rows after filter). The feature pipeline and per-tuple runtime use **input** cardinality (e.g. for pipeline scan size and percentages).

**Parsed_plans** (e.g. from **zero-shot-data/runs/parsed_plans**) only provide **output** cardinality per node: **est_card** and **act_card** are the rows **produced** by that operator. There is **no** field for “rows in the table” (input to the scan). So for a Seq Scan we know “500 rows came out” but not “how many rows the table has.”

**t3_jh** sets scan **input** cardinality in **QueryPlan.\_get_input_cardinality** (**jh_query_plan.py**):

- For **TableScan**:
  - If the scan’s **table_name** is **in** **db_statistics["table_stats_dict"]**: return **db_statistics["table_stats_dict"][tname]["reltuples"]**. For parsed_plans, that value is the one we put in from **\_normalize_plan_node** — i.e. **output** cardinality (act_card/est_card) of a scan for that table. So **input cardinality = output cardinality** (same number).
  - If the table is **not** in **table_stats_dict**: return **act_card** or **est_card** or **1** from the scan’s **plan_parameters**. So again we use **output** card as proxy, or **1** if both are missing.

So for **parsed_plans** in t3_jh:

- We **never** have true table size (input to the scan).
- We use **output cardinality** as the value for “input” (via **table_stats_dict** or directly from **plan_parameters**).
- Only when **act_card** and **est_card** are both missing do we use **1**.

Contrast with **zeroshot_to_t3** (the path that converts parsed plans to **Umbra** and uses the core T3 **QueryPlan**): there, when there is no schema, scan **inputCardinality** is set to **1** explicitly. So in that path, scan input is **1** when no table info is available. In **t3_jh**, scan input is **output card** (or 1 as last fallback), so we do **not** “leave them as 1” when we have act_card/est_card — we use output as proxy for input.

**Summary:** Parsed_plans give only output card; t3_jh treats **scan input cardinality = output cardinality** (via table_stats_dict or plan_parameters), and **1** only when no card is available.

---

## 6. Same pipeline as t3-Johannes (rewrite_children → BenchmarkedQuery)

From **rewrite_children** onward, **t3_jh** uses the **same** logic as t3-Johannes (implemented in **jh_dataloader**, **jh_query_plan**, **jh_operator_stages**, **jh_operators**, **jh_benchmarked_query**, **jh_features**, **jh_model**):

| Step | t3_jh module | What happens (same idea as t3-Johannes) |
|------|----------------|------------------------------------------|
| rewrite_children | **jh_dataloader** | **children** → **left** / **right** (Hash Join: left = build, right = probe) or **input**; **left_runtime** / **right_runtime** / **input_runtime**; prune Materialize. |
| annotate_op_id | **jh_dataloader** | **op_id** (1-based), **analyze_plan_id** (0-based). |
| extract_pipeline_infos | **jh_dataloader** | Build pipeline list from **act_time**, **left_runtime**, **right_runtime**; **add_order_to_pipelines** sets **start** / **stop**. |
| QueryPlan | **jh_query_plan** | Parse **plan_parameters** + **left** / **right** / **input** → **Operator**s; **\_get_input_cardinality** uses **db_statistics** (for scans: reltuples = output-card proxy in t3_jh) or **act_card** / **est_card** / 1. |
| build_pipelines | **jh_query_plan** | **operator_dict** by **analyze_plan_id**; for each pipeline, sort by precedes, **build_pipeline(ops, start, stop)** from **jh_operator_stages** → **Pipeline** with **ExecutionPhase** + **OperatorStage** (Scan/Build/Probe/PassThrough). |
| BenchmarkedQuery | **jh_benchmarked_query** | One runtime from **plan_runtime_ms**; **get_feature_matrix**, **get_pipeline_runtimes**, **get_per_tuple_pipeline_runtime_data** as in t3-Johannes. |
| FeatureMapper | **jh_features** | Per-pipeline feature vectors from **get_input_cardinality** / **get_right_input_cardinality** etc. (so scan input = our proxy above). |
| Model | **jh_model** | Per-tuple tree model; **assemble_x_y** in training uses **get_per_tuple_pipeline_runtime_data**. |

So **t3_jh** is “t3-Johannes pipeline + parsed_plans as input + db_statistics and scan input cardinality derived from output cards.”

---

## 7. Filter format: filter_columns → filter (jh_dataloader.py)

Parsed_plans use **filter_columns** (tree with **operator**, **children**). t3-Johannes expects **plan_parameters["filter"]** in a specific expression format. **\_normalize_plan_node** converts **filter_columns** to **filter** via **\_filter_columns_to_jh_expression** (AND/OR/NOT and leaf operators like =, >, LIKE, IN, etc.). So t3_jh adapts the zeroshot filter shape to what **jh_query_plan** and **jh_features** expect.

---

## 8. Diagnostics and skip reasons (jh_dataloader.py)

**load_parsed_plans_from_json** returns **(list of BenchmarkedQuery, diagnostics)**. For each file, **diagnostics** include **plans_total**, **added**, **skip_runtime**, **skip_exception**, **skip_act_time_le_zero**, **skip_runtime_validity**, and **exceptions** (with plan index and reason). So callers can see how many plans were dropped and why (e.g. unsupported operator, runtime validity, act_time ≤ 0).

---

## End-to-end summary

| Aspect | t3-Johannes | src/t3_jh |
|--------|-------------|-----------|
| **Input** | Workload-run plans (plan_parameters + children + plan_runtime_ms) + external **db_statistics** (real reltuples). | **parsed_plans** JSON (plan_parameters + children); **no** external db_statistics. |
| **Loader** | **gen_t3_dataset** → **read_workload_runs**. | **load_parsed_plans_from_json** → read **parsed_plans** from file(s). |
| **Plan normalization** | External **assign_additional_plan_info** (and optionally **extract_query_stats_for_plan**). | **\_normalize_plan_node**: set **table_name**, **filter** from filter_columns, fill **table_stats_global** with **output** card per table. |
| **db_statistics** | From workload loader (**table_stats_dict** with real **reltuples**). | Built from **table_stats_global**: **reltuples** = output cardinality (or 1 for **unknown**). |
| **Scan input cardinality** | From **db_statistics["table_stats_dict"][table]["reltuples"]** (true table size) when available. | From **table_stats_dict** → same value is **output** card; else **act_card** / **est_card** / **1**. So **input = output** (proxy) or **1**. |
| **Pipeline steps** | rewrite_children, annotate_op_id, extract_pipeline_infos, QueryPlan, build_pipelines, BenchmarkedQuery. | **Same**, implemented in jh_* modules. |
| **Output** | List of **BenchmarkedQuery** for training/eval. | Same; plus **diagnostics** per file. |

So **src/t3_jh** adds: (1) loading from **parsed_plans** instead of workload runs, (2) building **db_statistics** from the plans themselves (output cards only), (3) setting **scan input cardinality** to **output cardinality** (or 1) because parsed_plans do not provide table sizes, and (4) normalizing **filter_columns** to **filter** and **table_name** for scans. The rest of the pipeline is the same as t3-Johannes.
