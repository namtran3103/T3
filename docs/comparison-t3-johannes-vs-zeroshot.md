# Comparison: t3-Johannes vs src/zeroshot (Postgres → T3/Umbra)

Both codebases map **Postgres plans to T3/Umbra** (pipelines + feature vectors), but they differ in **plan representation**, **how pipelines are derived**, and **integration style**.

---

## 1. Plan Representation

| Aspect | **t3-Johannes** | **src/zeroshot** |
|--------|------------------|------------------|
| **Output shape** | Keeps **Postgres-shaped** plan: `plan_parameters.op_name` ("Seq Scan", "Hash Join", …), `left`/`right`/`input`, `est_card`/`act_card`. | Converts to **Umbra-shaped** plan: `operator` ("tablescan", "hashjoin", …), `cardinality`, `analyzePlanCardinality`, `producedIUs`, `restrictions`/`residuals`, `left`/`right`/`input`. |
| **Consumer** | Its own `QueryPlan` (in `models.t3.query_plan`) and operator/feature code that **understand Postgres** names and `plan_parameters`. | T3’s existing `src.query_plan` and `src.operators` / `src.operator_stages`, which expect **Umbra** plan format. |
| **Schema/cardinality** | Uses **real** DB: `db_statistics` (e.g. `table_stats_dict`, `reltuples`), `get_json_schema`, and `CardType` (pg/act/deepdb) for cardinality. | Uses a **minimal** DB (e.g. table `"unknown"`), no real schema; scans often use `inputCardinality = 1` and filter logic. |

So: Johannes extends the T3 stack to speak “Postgres” natively; zeroshot translates Postgres → Umbra so the rest of T3 stays Umbra-only.

---

## 2. Pipeline Extraction (Main Conceptual Difference)

**t3-Johannes — runtime-based**

- Pipelines are derived from **Postgres timing**: `act_time`, `left_runtime`, `right_runtime` from EXPLAIN ANALYZE.
- `extract_pipeline_infos` in `t3_dataloader.py`:
  - Treats **Sort / Aggregate / Simple Aggregate / Finalize Aggregate** as pipeline boundaries and assigns durations from those times.
  - For **Hash Join**: hash (build) side becomes its own pipeline with `left_runtime`, probe side continues; runtimes are consistent with PG.
  - For **Merge Join**: both sides are blocking; two pipelines with `left_runtime` and `right_runtime`.
  - For **Nested Loop**: inner (left) = one pipeline, outer (right) = continuing pipeline.
  - For **Index Nested Loop**: single pipeline (right/index side is pruned in the tree).
- It **asserts** that the sum of pipeline durations equals total plan runtime and normalizes start/stop so pipeline times are consistent.
- So pipeline **boundaries and durations** are driven by how Postgres actually spent time.

**zeroshot — structure-based**

- Pipelines are defined by **structural** rules in `_assign_pipelines`:
  - Pipeline breakers: **sort**, **groupby**, **temp** (including Materialize via `pgMaterialize`), and for joins the **build (left) subtree** gets a new pipeline.
- No use of `act_time` / `left_runtime` / `right_runtime` to **split** pipelines; the tree shape alone decides which ops go into which pipeline.
- **Start/stop per pipeline** are then **filled** from zeroshot node times: `_fill_times_zeroshot` uses `act_startup_cost` and `act_time`, then per pipeline takes min(start) and max(stop) of its operators.
- So pipeline **membership** is heuristic (by operator type and tree structure); **timing** is attached afterward.

**Summary**: Johannes is more faithful to observed execution (runtime-based, consistent with PG); zeroshot is simpler and more heuristic (structure-based, then time overlay).

---

## 3. Join and Aggregate Handling

**t3-Johannes**

- **rewrite_children** does careful normalization:
  - **Hash Join**: Ensures first child is the Hash side; **prunes** the Hash node and keeps its child; annotates `left_runtime` from the Hash subtree.
  - **Index Nested Loop**: Prunes the index-scan child and copies `idx_scan` into the join node; left = probe, right = index (no separate pipeline for index).
  - **Merge Join**: Keeps left/right; no special pruning.
  - **Nested Loop**: **Swaps** so left = inner (build), right = outer (probe) to match Umbra-style semantics.
  - **Finalize Aggregate / Simple Aggregate**: Collapses through Gather and Partial Aggregate to a single “Aggregate” and prunes those nodes.
  - **Materialize**: Pruned (replaced by child).
- Build = left, probe = right is enforced in one place with explicit PG-specific cases.

**zeroshot**

- **zeroshot_to_t3._convert_node**:
  - Hash Join: inner = build (left), outer = probe (right); if inner is Hash, unwraps one level.
  - Merge Join: mapped to hashjoin shape, inner/outer assigned.
  - Nested Loop: mapped to indexnljoin, children passed through.
  - Aggregate / Partial / Finalize: all mapped to **groupby** with one child; no Gather/Partial collapsing.
  - Materialize: mapped to **temp** with `pgMaterialize`; Hash → **temp**.
- Same “build left, probe right” idea, but implemented as a single conversion pass that emits Umbra-shaped nodes.

---

## 4. Operators and Stages

**t3-Johannes**

- **operators.py**: One enum for both Umbra and Postgres; `parse_operator_type(..., dbms="pg")` with `pg_name_map` (Seq Scan, Index Scan, Hash Join, Index Nested Loop, Nested Loop, Merge Join, Sort, Aggregate).
- **operator_stages.py**: Full handling for **IdxScan**, **NLJoin**, **MergeJoin**, **Aggregate** (Scan/Build/Probe as appropriate). No patch.

**zeroshot**

- Plan is converted to **Umbra** operator names only; Postgres-specific names never reach `src.operators`.
- **operator_stages_patch.py**: **Monkey-patches** `get_operator_stage` for **IndexNLJoin** so the “previous” op in a pipeline can be anywhere in the left/right **subtree** (not only direct child). Needed because zeroshot can emit Select/Temp between scan and join.

So: Johannes adds PG operators and stages in the core; zeroshot keeps core Umbra-only and uses one patch for IndexNLJoin.

---

## 5. Features and Training

**t3-Johannes**

- **features.py**: Its own `FeatureMapper` and `QualifiedFeature` with a full grid of (OperatorType, OperatorStage, Feature) and explicit handling for IdxScan, NLJoin, MergeJoin, Aggregate.
- Training path: `gen_t3_dataset` → `BenchmarkedQuery` → `assemble_x_y` (per-pipeline or per-query features and targets). Pipeline runtimes come from the **computed start/stop** (from PG timing).

**zeroshot**

- Uses T3’s **src.features.FeatureMapper** and **src.query_plan.QueryPlan** on the **converted** (Umbra-shaped) plan.
- Training scripts load zeroshot/raw JSON, call `zeroshot_plan_to_t3` / `raw_plan_to_t3`, then build `QueryPlan` and feature vectors. Pipeline times come from the **assigned** start/stop (min/max of node times per pipeline).

---

## 6. Why t3-Johannes Can Feel “More Sophisticated”

1. **Runtime-consistent pipelines**: Pipeline boundaries and durations are derived from PG’s `act_time` / `left_runtime` / `right_runtime`, with an explicit check that they add up to total runtime. Better for using pipeline runtimes as training targets.
2. **Single, explicit plan format**: One representation (Postgres) and a clear extension of the stack (PG operator types and stages) instead of a separate “zeroshot format” and a small patch.
3. **Schema and cardinality**: Real `db_statistics` and schema (table stats, card type) instead of a minimal DB and synthetic cardinality.
4. **Rigorous pipeline semantics**: Each join type and breaker (Sort, Aggregate, Merge Join, etc.) is handled with explicit pipeline rules and runtime math.
5. **Validation**: e.g. `check_plan_runtime_validity`, skipping plans with inconsistent runtimes; assertions on pipeline sum and overlap (see `benchmarked_query.check_pipeline_overlap`).
6. **No monkey-patch**: PG behavior is modeled in the main operator/stage logic rather than by patching one join type.

---

## 7. Summary Table

| Dimension | **t3-Johannes** | **src/zeroshot** |
|-----------|------------------|-------------------|
| Plan shape | Postgres-native (`plan_parameters`, PG op names) | Umbra-native (operator, cardinality, producedIUs, …) |
| Pipelines | From **actual runtimes** (act_time, left/right_runtime) | From **structure** (breakers + join build), then times filled from nodes |
| Schema | Real DB stats + schema | Minimal DB, no schema |
| PG operators | First-class in operators + operator_stages | Mapped away to Umbra; one patch for IndexNLJoin |
| Aggregates | Collapse Finalize/Gather/Partial → one Aggregate | Map all to groupby, no collapse |
| Code layout | Separate package (`models.t3.*`, training.*) | Inside T3 `src/`, uses `src.query_plan` / `src.features` |

**Bottom line**: Both are “Postgres to T3/Umbra mappers,” but **t3-Johannes** is built for **runtime-faithful, schema-aware** training with a single Postgres-native representation, while **zeroshot** is a **translation layer** that produces Umbra-shaped plans and structure-based pipelines with minimal schema, and keeps the rest of T3 unchanged except for the IndexNLJoin patch.
