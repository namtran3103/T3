# PG Operator-Level Features

This document describes the **operator-level features** in `PgFeatureMapper` (`src/pg_features.py`). These are **PG-native** features: no Umbra mapping, no stages. Each PostgreSQL operator is a distinct node (e.g. Hash is separate from Hash Join).

---

## 1. Overview

The feature vector has two parts:

1. **Part 1**: Existing `PgFeature` values (aggregate per-pipeline)
2. **Part 2**: Operator-level features for each PG operator type — count, in_card, out_card, in_percentage, out_percentage, etc.

**No stages.** PG plans have explicit operator nodes. Hash is a separate node; Hash Join is another. We do not map to Umbra’s Build/Probe/Scan/PassThrough stages.

---

## 2. Operators (from parsed_plans)

All 20 operators found in `zero-shot-data/runs/parsed_plans`:

| Operator | Category |
|----------|----------|
| Seq Scan, Parallel Seq Scan, Index Scan, Index Only Scan | Scans |
| Bitmap Heap Scan, Bitmap Index Scan, Parallel Bitmap Heap Scan, Parallel Index Scan, Parallel Index Only Scan | Scans |
| Hash | Build (hash table) |
| Materialize | Build (materialization) |
| Hash Join, Merge Join, Nested Loop | Joins |
| Sort | Sort |
| Aggregate, Partial Aggregate, Finalize Aggregate | Aggregates |
| Gather, Gather Merge | Pass-through / parallelism |

---

## 3. Feature Dimensions per Operator

| Operator | Dimensions |
|----------|------------|
| All scans | scan, out, expressions, empty_output |
| Hash | sink, input |
| Materialize | sink, input |
| Hash Join, Merge Join | input_card, right, out |
| Nested Loop | input, right_card, out |
| Sort | sink, input, out |
| Aggregate, Partial Aggregate, Finalize Aggregate | sink, input, out |
| Gather, Gather Merge | input, out |
| Other (unknown) | input, out |

---

## 4. Basic Features per Dimension

| Dimension | Features |
|-----------|----------|
| scan | in_card, in_size |
| sink | out_card, out_size |
| input | in_percentage |
| out | out_percentage |
| right | right_percentage |
| right_card | right_card |
| input_card | in_card |
| expressions | like_percentage, compare_percentage, in_expression_percentage, between_percentage, or_exp_percentage, starts_with_percentage |
| empty_output | empty_output |

---

## 5. Cardinality Semantics

Per `zeroshot_to_t3`: **left = build**, **right = probe** for Hash Join.

- **Hash Join, Merge Join**: `input_card` = right child (probe stream); `right_card` = left child (build size)
- **Nested Loop**: `right_card` = right child (inner index)

---

## 6. Vector Layout

```
[pg_est_card_sum, ..., pg_pipeline_root_act_card,  # existing PgFeature
 Seq_Scan_const, Seq_Scan_in_card, Seq_Scan_in_size, Seq_Scan_out_percentage, ...,
 Hash_const, Hash_out_card, Hash_in_percentage, ...,
 Hash_Join_const, Hash_Join_in_card, Hash_Join_right_percentage, Hash_Join_out_percentage, ...,
 ...,
 Other_const, Other_in_percentage, Other_out_percentage]  # fallback for unknown ops
```

Feature names use `op_name.replace(" ", "_")` (e.g. `Hash_Join`, `Seq_Scan`).

---

## 7. Implementation

- **Source:** `src/pg_features.py`
- **Operators:** `PG_OPERATORS`, `PG_OP_FEATURES`
- **Feature extraction:** `_extract_operator_features()` (no stage logic)
- **Order:** `_get_pipeline_ops_in_execution_order()` (post-order)
- **Unknown operators:** `Other` slot with input, out dimensions

---

## 8. Breaking Change

Feature vector size and layout change. Existing zeroshot models must be retrained.
