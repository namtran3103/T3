# Zero-Shot Query Processing: Step-by-Step Example

This document explains how a zero-shot parsed plan (from `zero-shot-data/runs/parsed_plans`) is processed by `zeroshot_to_t3.py` and `pg_features.py` to produce feature vectors for T3 runtime prediction.

## Example: Hash Join of Two Scans

We use a minimal plan: a **Hash Join** with two **Seq Scan** children. This matches the structure found in parsed_plans JSON files.

### 1. Zero-Shot Input Format

Zero-shot plans live in JSON files with a `parsed_plans` array. Each plan is a tree of nodes:

- **`plan_parameters`**: operator metadata (op_name, est_card, act_card, act_time, filter_columns, etc.)
- **`children`**: list of child nodes (order matters for joins)

Our synthetic example:

```
Hash Join (root)
├── Seq Scan (table 1)     ← outer/probe side
└── Hash
    └── Seq Scan (table 2) ← inner/build side
```

In zero-shot, the Hash Join has:
- `children[0]` = outer (probe) = Seq Scan on table 1
- `children[1]` = Hash node, whose child is the build-side Seq Scan on table 2

**Raw zero-shot plan (simplified):**

```json
{
  "plan_parameters": {
    "op_name": "Hash Join",
    "est_card": 500.0,
    "act_card": 480.0,
    "act_time": 10.5,
    "filter_columns": {"operator": "=", "children": []}
  },
  "children": [
    {
      "plan_parameters": {
        "op_name": "Seq Scan",
        "table": 1,
        "est_card": 1000.0,
        "act_card": 950.0,
        "act_time": 5.2,
        "filter_columns": {"operator": "=", "column": 1, "literal": 42, "children": []}
      },
      "children": []
    },
    {
      "plan_parameters": {"op_name": "Hash", "act_card": 180.0, "act_time": 1.1},
      "children": [
        {
          "plan_parameters": {
            "op_name": "Seq Scan",
            "table": 2,
            "est_card": 200.0,
            "act_card": 180.0,
            "act_time": 0.8,
            "filter_columns": null
          },
          "children": []
        }
      ]
    }
  ]
}
```

---

## 2. Step 1: Load and Convert (`zeroshot_to_t3.py`)

### 2.1 Entry Point

```python
from src.zeroshot.zeroshot_to_t3 import zeroshot_plan_to_t3

t3_plan = zeroshot_plan_to_t3(zs_plan, use_actual_card=True)
```

Or from a file:

```python
from src.zeroshot.zeroshot_to_t3 import convert_file_to_t3

t3_plans = convert_file_to_t3("path/to/parsed_plans/imdb/job-light_c8220.json")
```

### 2.2 Node Conversion (`_convert_node`)

Each zero-shot node is recursively converted to T3/Umbra-style format:

| Zero-shot op_name | T3 operator | Notes |
|-------------------|-------------|-------|
| Seq Scan, Index Scan, ... | `tablescan` | `tablename: "unknown"`, `inputCardinality: 1` |
| Hash Join | `join` + `physicalOperator: "hashjoin"` | left=build, right=probe |
| Hash | `temp` | Build side of hash join; child becomes `left` of join |
| Merge Join | `join` + `hashjoin` | Same mapping as Hash Join |
| Nested Loop | `join` + `indexnljoin` | left=probe, right=build |

**Important:** For Hash Join, zero-shot has `children[0]=outer`, `children[1]=Hash(build)`. T3 uses `left=build`, `right=probe`. So:

- `left` ← inner child (Hash’s child = Seq Scan on table 2)
- `right` ← outer child (Seq Scan on table 1)

### 2.3 Attaching `pg` Payload

Every converted node gets `out["pg"] = dict(plan_parameters)`. This preserves the original zero-shot fields (`op_name`, `est_card`, `act_card`, `act_time`, `filter_columns`, etc.) for `PgFeatureMapper`.

### 2.4 Filter Conversion

`filter_columns` on scans is converted to a restriction tree:

- `operator: "="` → `{"expression": "compare", "direction": "="}`
- `AND`/`OR`/`NOT` → recursive `expression`/`input` structure

### 2.5 Output of `zeroshot_plan_to_t3`

```json
{
  "plan": {
    "operator": "join",
    "analyzePlanId": 1,
    "physicalOperator": "hashjoin",
    "left": {
      "operator": "tablescan",
      "analyzePlanId": 2,
      "tablename": "unknown",
      "pg": {"op_name": "Seq Scan", "table": 2, "act_card": 180.0, ...}
    },
    "right": {
      "operator": "tablescan",
      "analyzePlanId": 3,
      "restrictions": [{"expression": "compare", "direction": "="}],
      "pg": {"op_name": "Seq Scan", "table": 1, "act_card": 950.0, ...}
    },
    "pg": {"op_name": "Hash Join", "act_card": 480.0, ...}
  },
  "analyzePlanPipelines": [
    {"operators": [2], "duration": 0.0052},
    {"operators": [1, 3], "duration": 0.0105}
  ],
  "ius": [{"iu": "default", "estimatedSize": 8}]
}
```

---

## 3. Step 2: Pipeline Assignment

Pipelines are assigned by `_assign_pipelines`:

- **Pipeline breakers:** Sort, Aggregate, Materialize, Hash (build side of hash join)
- **Hash Join:** Build side (left) stays in current pipeline; join + probe (right) go to the next pipeline

For our example:

| Pipeline | Operators | Meaning |
|----------|------------|---------|
| 0 | [2] | Build pipeline: Seq Scan on table 2 |
| 1 | [1, 3] | Probe pipeline: Hash Join + Seq Scan on table 1 |

---

## 4. Step 3: Feature Extraction (`pg_features.py`)

### 4.1 Entry Point

```python
from src.pg_features import PgFeatureMapper

mapper = PgFeatureMapper()
feature_matrix = mapper.get_pipeline_estimation_matrix(t3_plan)
# shape: (num_pipelines, num_features)
```

### 4.2 How Features Are Built

`PgFeatureMapper` uses only the T3 plan dict (no Umbra `QueryPlan`). It:

1. **Collects nodes by ID:** `_collect_nodes_by_id(root, id_to_node)`
2. **For each pipeline:** iterates over `operators` (analyzePlanIds)
3. **Reads `node["pg"]`** for each operator in that pipeline

### 4.3 Pipeline-Level Features (`_extract_pipeline_pg_features`)

Aggregated over all operators in the pipeline:

| Feature | Description |
|---------|-------------|
| `pg_act_card_sum` | Sum of act_card (or est_card) |
| `pg_act_card_max` | Max act_card |
| `pg_act_time_sum` | Sum of act_time (ms) |
| `pg_est_width_avg` | Average est_width |
| `pg_num_scan` | Count of scan operators |
| `pg_num_join` | Count of join operators |
| `pg_scan_act_card_sum` | Sum of act_card over scans only |
| `pg_scan_has_filter` | 1 if any scan has filter_columns |
| `pg_filter_compare_count` | Count of compare expressions (from filter_columns tree) |
| `pg_filter_and_count`, `pg_filter_or_count`, ... | Filter structure counts |
| `pg_pipeline_act_time_ms` | Pipeline duration (from analyzePlanPipelines) |
| `pg_pipeline_root_act_card` | Root node’s act_card |

### 4.4 Operator-Level Features (`_extract_operator_features`)

Per-operator features, summed by operator type (Seq Scan, Hash Join, etc.):

- **Scan:** `in_card`, `in_size`, `out_percentage`, expression percentages (like, compare, in, or)
- **Hash Join:** `input_card`, `right_percentage`, `out_percentage`
- **Hash/Materialize:** `out_card`, `out_size`, `in_percentage`

Percentages are relative to `pipeline_scan_card` (sum of scan act_cards in the pipeline).

### 4.5 Example Output for Our Plan

**Pipeline 0 (build):** One Seq Scan (id 2)

- `pg_num_scan = 1`, `pg_scan_act_card_sum = 180`
- Operator features for Seq Scan: `in_card`, `out_percentage`, etc.

**Pipeline 1 (probe):** Hash Join (id 1) + Seq Scan (id 3)

- `pg_num_scan = 1`, `pg_num_join = 1`
- `pg_scan_act_card_sum = 950` (only the probe scan)
- Operator features for both Hash Join and Seq Scan

---

## 5. End-to-End Flow

```
parsed_plans JSON
       │
       ▼
zeroshot_plan_to_t3(zs_plan)
       │
       ├─ _convert_node (recursive)
       │    ├─ Map op_name → T3 operator
       │    ├─ Set left/right/input from children
       │    └─ Attach pg = plan_parameters
       │
       ├─ _assign_pipelines
       │    └─ Split at Hash, Sort, Aggregate, Materialize
       │
       └─ _fill_times_zeroshot
            └─ Copy act_startup_cost, act_time to pipelines
       │
       ▼
T3 plan dict { plan, analyzePlanPipelines, ius }
       │
       ▼
PgFeatureMapper.get_pipeline_estimation_matrix(t3_plan)
       │
       ├─ _collect_nodes_by_id
       ├─ For each pipeline:
       │    ├─ _extract_pipeline_pg_features (aggregate PG features)
       │    └─ _extract_operator_features (per-operator sums)
       │
       ▼
feature_matrix: (num_pipelines × num_features)
```

---

## 6. Summary

| Stage | Module | Input | Output |
|-------|--------|-------|--------|
| Load | `zeroshot_to_t3` | JSON path or plan dict | List of T3 plan dicts |
| Convert | `zeroshot_plan_to_t3` | Zero-shot plan | T3 plan (plan, pipelines, ius) |
| Features | `PgFeatureMapper.get_pipeline_estimation_matrix` | T3 plan dict | (P × F) matrix |

The feature matrix is used by T3 models (e.g. `PerTupleTreeModel`) for runtime prediction. Zeroshot training scripts use `PgFeatureMapper` instead of the Umbra `FeatureMapper` because parsed plans have no schema; features come entirely from `plan_parameters` attached as `pg` on each node.
