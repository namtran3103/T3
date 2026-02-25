# Holdout max-error debug: tpc_h

Holdout model: `model_jh_holdout_tpc_h.txt`
Test queries: 15000
Top-10 highest q-error queries.

Zeroshot model: `model_zero_holdout_tpc_h_v2.txt` (for comparison).

## Rank 1: index_workload_100k_s2_c8220_1588 (q_error = 38144990000.0000)

- **actual** = 3.814499 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 38144990000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1588

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 5583.0
- actual runtime = 3.814499 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 5583.0
    141: Aggregate_Scan_in_size = 25.0
    142: Aggregate_Scan_out_percentage = 0.00017911517105498835


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 1.336269 s
- **q_error (zeroshot)** = 2.8546

(Zeroshot has 4 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 857324.0
    27: Select_PassThrough_out_percentage = 1714648.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 857324.0
    41: HashJoin_Build_out_size = 21.0
    42: HashJoin_Build_in_percentage = 857324.0

## Rank 2: index_workload_100k_s2_c8220_3207 (q_error = 24601560000.0000)

- **actual** = 2.460156 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 24601560000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 3207

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 5970.0
- actual runtime = 2.460156 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 5970.0
    141: Aggregate_Scan_in_size = 12.0
    142: Aggregate_Scan_out_percentage = 0.00016750418760469013


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 1.487059 s
- **q_error (zeroshot)** = 1.6544

(Zeroshot has 4 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 1636893.0
    27: Select_PassThrough_out_percentage = 2864142.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 1227249.0
    41: HashJoin_Build_out_size = 12.0
    42: HashJoin_Build_in_percentage = 1227249.0

## Rank 3: index_workload_100k_s2_c8220_3368 (q_error = 17872770000.0000)

- **actual** = 1.787277 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 17872770000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 3368

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 33898.0
- actual runtime = 1.787277 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 33898.0
    141: Aggregate_Scan_in_size = 9.0
    142: Aggregate_Scan_out_percentage = 2.9500265502389522e-05


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.983038 s
- **q_error (zeroshot)** = 1.8181

(Zeroshot has 4 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 516907.0
    27: Select_PassThrough_out_percentage = 929413.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 412506.0
    41: HashJoin_Build_out_size = 8.0
    42: HashJoin_Build_in_percentage = 412506.0

## Rank 4: index_workload_100k_s2_c8220_3481 (q_error = 11650350000.0000)

- **actual** = 1.165035 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 11650350000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 3481

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 16729.0
- actual runtime = 1.165035 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 16729.0
    141: Aggregate_Scan_in_size = 4.0
    142: Aggregate_Scan_out_percentage = 5.9776436128878e-05


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.933593 s
- **q_error (zeroshot)** = 1.2479

(Zeroshot has 4 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 581088.0
    27: Select_PassThrough_out_percentage = 747717.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 166629.0
    41: HashJoin_Build_out_size = 8.0
    42: HashJoin_Build_in_percentage = 166629.0

## Rank 5: index_workload_100k_s2_c8220_1722 (q_error = 11117740000.0000)

- **actual** = 1.111774 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 11117740000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1722

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 15247.0
- actual runtime = 1.111774 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 15247.0
    142: Aggregate_Scan_out_percentage = 6.558667278808946e-05


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.786889 s
- **q_error (zeroshot)** = 1.4129

(Zeroshot has 4 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 300589.0
    27: Select_PassThrough_out_percentage = 430185.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 129596.0
    41: HashJoin_Build_out_size = 8.0
    42: HashJoin_Build_in_percentage = 129596.0

## Rank 6: index_workload_100k_s2_c8220_1492 (q_error = 9512330000.0000)

- **actual** = 0.951233 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 9512330000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1492

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 43144.0
- actual runtime = 0.951233 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 43144.0
    141: Aggregate_Scan_in_size = 8.0
    142: Aggregate_Scan_out_percentage = 2.3178193955127018e-05


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.372621 s
- **q_error (zeroshot)** = 2.5528

(Zeroshot has 3 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 1375759.0
    27: Select_PassThrough_out_percentage = 1418903.0

## Rank 7: index_workload_100k_s2_c8220_1687 (q_error = 8153620000.0000)

- **actual** = 0.815362 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 8153620000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1687

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 23717.0
- actual runtime = 0.815362 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 23717.0
    141: Aggregate_Scan_in_size = 8.0
    142: Aggregate_Scan_out_percentage = 4.216384871611081e-05


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.271607 s
- **q_error (zeroshot)** = 3.0020

(Zeroshot has 3 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 1090332.0
    27: Select_PassThrough_out_percentage = 1114049.0

## Rank 8: index_workload_100k_s2_c8220_4219 (q_error = 7826980000.0000)

- **actual** = 0.782698 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 7826980000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 4219

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 19727.0
- actual runtime = 0.782698 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 19727.0
    141: Aggregate_Scan_in_size = 8.0
    142: Aggregate_Scan_out_percentage = 5.069194504993157e-05


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.272793 s
- **q_error (zeroshot)** = 2.8692

(Zeroshot has 3 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 1091124.0
    27: Select_PassThrough_out_percentage = 1110851.0

## Rank 9: index_workload_100k_s2_c8220_108 (q_error = 7702380000.0000)

- **actual** = 0.770238 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 7702380000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 108

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 21.0
- actual runtime = 0.770238 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 21.0
    141: Aggregate_Scan_in_size = 4.0
    142: Aggregate_Scan_out_percentage = 0.047619047619047616


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.271607 s
- **q_error (zeroshot)** = 2.8359

(Zeroshot has 3 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 1091124.0
    27: Select_PassThrough_out_percentage = 1091145.0

## Rank 10: index_workload_100k_s2_c8220_3151 (q_error = 7501010000.0000)

- **actual** = 0.750101 s
- **pred (holdout)** = 0.000000 s
- **q_error** = 7501010000.0000
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 3151

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 2480.0
- actual runtime = 0.750101 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 2480.0
    141: Aggregate_Scan_in_size = 8.0
    142: Aggregate_Scan_out_percentage = 0.0004032258064516129


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.260801 s
- **q_error (zeroshot)** = 2.8761

(Zeroshot has 3 pipelines vs JH 1 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 857324.0
    27: Select_PassThrough_out_percentage = 859804.0
