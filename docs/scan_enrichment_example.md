# Scan enrichment: one worked example

This document traces **one concrete scan** through raw EXPLAIN ANALYZE text → enrichment step → parsed plan fields → zeroshot mapper usage, so “scan enrichment” is clear with a single end-to-end example.

## Example: first scan in `job_full_c8220` (IMDB), plan 0

### 1. Raw JSON (EXPLAIN ANALYZE text)

The raw file (e.g. `/Users/namtran/Downloads/zero-shot-data/runs/raw/imdb_full/job_full_c8220.json`) has, for a query, `query_list[i].analyze_plans[0]`: a list of text lines from `EXPLAIN (ANALYZE, ...)`.

For this example, the relevant lines look like:

```text
  ->  Parallel Seq Scan on cast_info ci  (cost=0.00..479243.90 rows=11655 width=12)
        Filter: (((note)::text ~~ '%(voice)%'::text) AND ...
        Rows Removed by Filter: 12070685
```

From this, the enrichment code extracts:

- **`act_card`**: from the scan line’s **actual** stats, i.e. the `rows=…` in `(actual time=… rows=Z loops=…)` (regex `rows=(\d+)`). In the run we inspected, the first matching scan in the first plan had `act_card = 10763` (same query can have small variance across plans).
- **`rows_removed_by_filter`**: from the next few lines, regex `Rows Removed by Filter:\s*(\d+)` → **12,070,685**.

So in the raw we have: **rows that passed the filter** (`act_card`) and **rows removed by the filter** (`rows_removed_by_filter`). That is all the raw provides for this scan.

### 2. Parsed plan **before** enrichment

In the parsed plan (same structure as in `parsed_plans` or before enrichment in `parsed_new`), the corresponding scan node has only what the parser produced, e.g.:

- `plan_parameters.op_name`: `"Parallel Seq Scan"`
- `plan_parameters.act_card`: `10763.0` (from the parser, which also reads the EXPLAIN output)
- `plan_parameters.input_cardinality`: **not set**
- `plan_parameters.rows_removed_by_filter`: **not set**
- `plan_parameters.overall_selectivity`: **not set**

So **before** enrichment, the scan has **no** input cardinality or filter selectivity in the parsed JSON.

### 3. Enrichment step (what gets written)

Enrichment (`enrich_parsed_plans.py`) does the following for this scan:

1. **Match scans**: It walks the **raw** plan lines with `find_all_scans_in_raw()` (regex for `Seq Scan` / `Parallel Seq Scan` / etc.), and for each scan line it calls `extract_scan_info_from_raw()` to get `act_card` (from `rows=…`) and `rows_removed_by_filter` (from “Rows Removed by Filter” in the next few lines). It builds a list of `(line_index, scan_info)` in **plan order**.
2. **Match parsed tree**: It walks the **parsed** plan tree **depth-first** and, for each node whose `op_name` is one of the scan types, it assigns the next entry from that list. It optionally refines the match by comparing `act_card` (parsed node vs raw) so that reordering doesn’t mix up scans.
3. **Write only when raw has filter info**: For this scan, `rows_removed_by_filter` is present and &gt; 0, so the code sets on the **parsed** node’s `plan_parameters`:
   - `rows_removed_by_filter` = **12,070,685**
   - `input_cardinality` = **act_card + rows_removed_by_filter** = 10,763 + 12,070,685 = **12,081,448**
   - `overall_selectivity` = **act_card / input_cardinality** = 10,763 / 12,081,448 ≈ **0.00089**

Scans that have no “Rows Removed by Filter” line (e.g. no filter, or index scans that don’t report it) are **not** enriched with these fields; they keep no `input_cardinality` / `overall_selectivity` in the parsed plan.

### 4. Parsed plan **after** enrichment

After enrichment, the same scan node in `data/zero-shot-data/parsed_new/imdb_full/job_full_c8220.json` (first plan) looks like:

- `plan_parameters.op_name`: `"Parallel Seq Scan"`
- `plan_parameters.act_card`: `10763.0`
- `plan_parameters.input_cardinality`: **12081448.0**
- `plan_parameters.rows_removed_by_filter`: **12070685**
- `plan_parameters.overall_selectivity`: **≈ 0.00089087**

So the **only** thing enrichment adds for this scan is those three numbers, derived from the raw EXPLAIN ANALYZE text.

### 5. Zeroshot mapper usage (`zeroshot_to_t3.py`)

In the T3 mapper, for a **TableScan** (parsed “Seq Scan” / “Parallel Seq Scan” / etc.):

- **Input cardinality**: If the node has `input_cardinality` from enrichment and it is in `[1, 1e15)`, the mapper uses it as **`inputCardinality`** in the T3 plan; otherwise it uses **1** (Option B: real cardinality only when enriched).
- **Selectivity**: The mapper can use `overall_selectivity` (and/or expression-level selectivities) to build the restriction tree and root `estimatedSelectivity` that the core uses for features.

So for this scan, the enriched values **12081448** and **~0.00089** flow into the T3 plan and into pipeline/percentage and scan-cardinality features; without enrichment, this scan would have `inputCardinality = 1` and no real scan selectivity from the raw.

---

## Summary

| Stage        | What we have for this scan |
|-------------|----------------------------|
| **Raw**     | Scan line with `rows=10763` (or 11655 in another run), next line “Rows Removed by Filter: 12070685”. |
| **Parsed (before)** | `act_card=10763`, no `input_cardinality` / `rows_removed_by_filter` / `overall_selectivity`. |
| **Enrichment** | From raw: set `rows_removed_by_filter=12070685`, `input_cardinality=12081448`, `overall_selectivity≈0.00089` on the parsed scan node. |
| **Parsed (after)** | Same node now has those three fields. |
| **Zeroshot → T3** | Uses `input_cardinality` as real scan input cardinality and the selectivity for features; without enrichment, scan would use `inputCardinality=1` and no raw-derived selectivity. |

So **scan enrichment** means: for each scan in the parsed plan, if the matching raw EXPLAIN ANALYZE text has “Rows Removed by Filter”, we add **input_cardinality**, **rows_removed_by_filter**, and **overall_selectivity** to that scan node so the zeroshot mapper can use real scan cardinalities and selectivities instead of defaults.
