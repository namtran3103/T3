# Holdout max-error debug: tpc_h

Holdout model: `model_jh_holdout_v5.txt`
Test queries: 15000
Top-10 highest q-error queries.

Zeroshot model: `model_zero_holdout_tpc_h_v2.txt` (for comparison).

## Rank 1: index_workload_100k_s2_c8220_942 (q_error = 603.2708)

- **actual** = 0.151034 s
- **pred (holdout)** = 91.114400 s
- **q_error** = 603.2708
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 942

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 328.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 328.0
    141: Aggregate_Scan_in_size = 8.0
    142: Aggregate_Scan_out_percentage = 0.003048780487804878

#### Pipeline 1
- scan_size = 300091.0
- actual runtime = 0.150801 s
- pred runtime = 91.114372 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 35.0
    3: TableScan_Scan_out_percentage = 0.00011663128850915223
    5: TableScan_Scan_compare_percentage = 2.0
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.00037322012322928713
    27: Select_PassThrough_out_percentage = 0.0011196603696878615
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    123: NLJoin_Probe_const = 3.0
    124: NLJoin_Probe_in_percentage = 1.6661612644164605e-05
    125: NLJoin_Probe_right_card = 483.0
    126: NLJoin_Probe_out_percentage = 0.0018394420359157723
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 32.0
    138: Aggregate_Build_in_percentage = 0.0010930017894571979

#### Pipeline 2
- scan_size = 1.0
- actual runtime = 0.000006 s
- pred runtime = 0.000005 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 328.0
    121: NLJoin_Build_out_size = 8.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 3
- scan_size = 1.0
- actual runtime = 0.000189 s
- pred runtime = 0.000006 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 112.0
    121: NLJoin_Build_out_size = 8.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 4
- scan_size = 3.0
- actual runtime = 0.000038 s
- pred runtime = 0.000017 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 112.0
    121: NLJoin_Build_out_size = 16.0
    122: NLJoin_Build_in_percentage = 1.0


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.625455 s
- **q_error (zeroshot)** = 4.1412

#### Zeroshot pipeline 0 features (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 3.0
    26: Select_PassThrough_in_percentage = 300203.0
    27: Select_PassThrough_out_percentage = 300462.0
    47: IndexNLJoin_Probe_const = 3.0
    48: IndexNLJoin_Probe_in_percentage = 483.0
    49: IndexNLJoin_Probe_right_card = 3.0
    50: IndexNLJoin_Probe_out_percentage = 552.0

#### Zeroshot pipeline 1 features (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    3: TableScan_Scan_out_percentage = 3.0
    5: TableScan_Scan_compare_percentage = 1.0

#### Zeroshot pipeline 2 features (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    3: TableScan_Scan_out_percentage = 1.0

#### Zeroshot pipeline 3 features (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    3: TableScan_Scan_out_percentage = 1.0
    5: TableScan_Scan_compare_percentage = 1.0

#### Zeroshot pipeline 4 features (non-zero):
    68: GroupBy_Scan_const = 1.0
    69: GroupBy_Scan_out_card = 1.0
    70: GroupBy_Scan_out_size = 32.0
    71: GroupBy_Scan_out_percentage = 1.0

## Rank 2: index_workload_100k_s2_c8220_1902 (q_error = 580.8631)

- **actual** = 0.407272 s
- **pred (holdout)** = 0.000701 s
- **q_error** = 580.8631
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1902

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 445.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 445.0
    141: Aggregate_Scan_in_size = 17.0
    142: Aggregate_Scan_out_percentage = 0.0022471910112359553

#### Pipeline 1
- scan_size = 445.0
- actual runtime = 0.407272 s
- pred runtime = 0.000701 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 64.0
    138: Aggregate_Build_in_percentage = 1.0


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.223740 s
- **q_error (zeroshot)** = 1.8203

(Zeroshot has 3 pipelines vs JH 2 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 1.0
    27: Select_PassThrough_out_percentage = 445.0

## Rank 3: index_workload_100k_s2_c8220_4855 (q_error = 466.3796)

- **actual** = 0.169430 s
- **pred (holdout)** = 79.018703 s
- **q_error** = 466.3796
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 4855

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 1557.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 1557.0
    141: Aggregate_Scan_in_size = 10.0
    142: Aggregate_Scan_out_percentage = 0.0006422607578676942

#### Pipeline 1
- scan_size = 351.0
- actual runtime = 0.140652 s
- pred runtime = 78.934999 s
Feature vector (non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 1.4786324786324787
    27: Select_PassThrough_out_percentage = 4.435897435897436
    123: NLJoin_Probe_const = 1.0
    124: NLJoin_Probe_in_percentage = 1.7065527065527066
    125: NLJoin_Probe_right_card = 71.0
    126: NLJoin_Probe_out_percentage = 1.4786324786324787
    127: MergeJoin_Probe_const = 1.0
    128: MergeJoin_Probe_in_percentage = 1.0
    129: MergeJoin_Probe_right_card = 635.0
    130: MergeJoin_Probe_out_percentage = 0.2022792022792023
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 32.0
    138: Aggregate_Build_in_percentage = 4.435897435897436

#### Pipeline 2
- scan_size = 599.0
- actual runtime = 0.001504 s
- pred runtime = 0.003073 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 519.0
    121: NLJoin_Build_out_size = 10.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 3
- scan_size = 635.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 2019.0
    79: Sort_Scan_in_size = 4.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 71.0
    133: MergeJoin_Build_out_size = 18.0
    134: MergeJoin_Build_in_percentage = 0.552755905511811

#### Pipeline 4
- scan_size = 351.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 351.0
    79: Sort_Scan_in_size = 14.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 71.0
    133: MergeJoin_Build_out_size = 18.0
    134: MergeJoin_Build_in_percentage = 1.0

#### Pipeline 5
- scan_size = 10000.0
- actual runtime = 0.003947 s
- pred runtime = 0.005559 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 10000.0
    3: TableScan_Scan_out_percentage = 1.0
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 5.0
    45: HashJoin_Probe_right_percentage = 1.0
    46: HashJoin_Probe_out_percentage = 0.2019
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 635.0
    74: Sort_Build_out_size = 4.0
    75: Sort_Build_in_percentage = 0.2019
    76: Sort_Build_out_percentage = 0.0635

#### Pipeline 6
- scan_size = 25.0
- actual runtime = 0.000047 s
- pred runtime = 0.000094 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 25.0
    3: TableScan_Scan_out_percentage = 1.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 5.0
    41: HashJoin_Build_out_size = 4.0
    42: HashJoin_Build_in_percentage = 0.2
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 1.0
    45: HashJoin_Probe_right_percentage = 1.0
    46: HashJoin_Probe_out_percentage = 0.2

#### Pipeline 7
- scan_size = 4.0
- actual runtime = 0.000022 s
- pred runtime = 0.000005 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 4.0
    3: TableScan_Scan_out_percentage = 0.25
    5: TableScan_Scan_compare_percentage = 1.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 1.0
    41: HashJoin_Build_out_size = 4.0
    42: HashJoin_Build_in_percentage = 0.25

#### Pipeline 8
- scan_size = 11729.0
- actual runtime = 0.023258 s
- pred runtime = 0.074973 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 351.0
    3: TableScan_Scan_out_percentage = 0.029925824878506268
    5: TableScan_Scan_compare_percentage = 3.0
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 351.0
    74: Sort_Build_out_size = 14.0
    75: Sort_Build_in_percentage = 0.029925824878506268
    76: Sort_Build_out_percentage = 0.029925824878506268
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 1.223212 s
- **q_error (zeroshot)** = 7.2196

(Zeroshot has 8 pipelines vs JH 9 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.8173228346456692
    27: Select_PassThrough_out_percentage = 2.451968503937008
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 635.0
    45: HashJoin_Probe_right_percentage = 0.552755905511811
    46: HashJoin_Probe_out_percentage = 0.11181102362204724
    47: IndexNLJoin_Probe_const = 1.0
    48: IndexNLJoin_Probe_in_percentage = 0.11181102362204724
    49: IndexNLJoin_Probe_right_card = 1.0
    50: IndexNLJoin_Probe_out_percentage = 0.8173228346456692
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 2019.0
    79: Sort_Scan_in_size = 8.0
    80: Sort_Scan_out_percentage = 1.0

## Rank 4: workload_100k_s1_c8220_3434 (q_error = 399.9622)

- **actual** = 9.409261 s
- **pred (holdout)** = 3763.348402 s
- **q_error** = 399.9622
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/workload_100k_s1_c8220.json` plan_index = 3434

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 102.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 102.0
    141: Aggregate_Scan_in_size = 4.0
    142: Aggregate_Scan_out_percentage = 0.00980392156862745

#### Pipeline 1
- scan_size = 297425.0
- actual runtime = 5.313690 s
- pred runtime = 3761.378492 s
Feature vector (non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.00011431453307556527
    27: Select_PassThrough_out_percentage = 0.0003429435992266958
    123: NLJoin_Probe_const = 3.0
    124: NLJoin_Probe_in_percentage = 1.208977053038581
    125: NLJoin_Probe_right_card = 174.0
    126: NLJoin_Probe_out_percentage = 0.0005782970496763891
    127: MergeJoin_Probe_const = 1.0
    128: MergeJoin_Probe_in_percentage = 1.0
    129: MergeJoin_Probe_right_card = 110.0
    130: MergeJoin_Probe_out_percentage = 0.00012103891737412793
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 40.0
    138: Aggregate_Build_in_percentage = 0.0003429435992266958

#### Pipeline 2
- scan_size = 8509.0
- actual runtime = 0.014373 s
- pred runtime = 0.054005 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 8509.0
    3: TableScan_Scan_out_percentage = 17.628393465742157
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 102.0
    121: NLJoin_Build_out_size = 4.0
    122: NLJoin_Build_in_percentage = 17.628393465742157

#### Pipeline 3
- scan_size = 10000.0
- actual runtime = 0.001889 s
- pred runtime = 0.034261 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 10000.0
    3: TableScan_Scan_out_percentage = 0.958
    5: TableScan_Scan_compare_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 34.0
    121: NLJoin_Build_out_size = 8.0
    122: NLJoin_Build_in_percentage = 0.958

#### Pipeline 4
- scan_size = 86297.0
- actual runtime = 0.018488 s
- pred runtime = 0.244043 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 86297.0
    3: TableScan_Scan_out_percentage = 2.3175776678215927
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 36.0
    121: NLJoin_Build_out_size = 16.0
    122: NLJoin_Build_in_percentage = 2.3175776678215927

#### Pipeline 5
- scan_size = 110.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 104.0
    79: Sort_Scan_in_size = 8.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 36.0
    133: MergeJoin_Build_out_size = 20.0
    134: MergeJoin_Build_in_percentage = 2703.8636363636365

#### Pipeline 6
- scan_size = 297425.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 298737.0
    79: Sort_Scan_in_size = 12.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 36.0
    133: MergeJoin_Build_out_size = 20.0
    134: MergeJoin_Build_in_percentage = 1.0

#### Pipeline 7
- scan_size = 534398.0
- actual runtime = 0.170206 s
- pred runtime = 0.007496 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 534398.0
    3: TableScan_Scan_out_percentage = 0.00019461150677959124
    5: TableScan_Scan_compare_percentage = 1.0
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 110.0
    74: Sort_Build_out_size = 8.0
    75: Sort_Build_in_percentage = 0.00019461150677959124
    76: Sort_Build_out_percentage = 0.00020583909370918305

#### Pipeline 8
- scan_size = 2000405.0
- actual runtime = 3.495769 s
- pred runtime = 1.355386 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 2000405.0
    3: TableScan_Scan_out_percentage = 0.7499071438033799
    5: TableScan_Scan_compare_percentage = 1.0
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 298723.0
    45: HashJoin_Probe_right_percentage = 0.7499071438033799
    46: HashJoin_Probe_out_percentage = 0.149338259002552
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 297425.0
    74: Sort_Build_out_size = 12.0
    75: Sort_Build_in_percentage = 0.149338259002552
    76: Sort_Build_out_percentage = 0.14868239181565732

#### Pipeline 9
- scan_size = 1383339.0
- actual runtime = 0.394846 s
- pred runtime = 0.274718 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1383339.0
    3: TableScan_Scan_out_percentage = 0.21594345276175977
    5: TableScan_Scan_compare_percentage = 1.0
    39: HashJoin_Build_const = 1.0
    40: HashJoin_Build_out_card = 298723.0
    41: HashJoin_Build_out_size = 8.0
    42: HashJoin_Build_in_percentage = 0.21594345276175977


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 2.232237 s
- **q_error (zeroshot)** = 4.2152

(Zeroshot has 9 pipelines vs JH 10 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.3090909090909091
    27: Select_PassThrough_out_percentage = 0.9272727272727272
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 110.0
    45: HashJoin_Probe_right_percentage = 2703.8636363636365
    46: HashJoin_Probe_out_percentage = 0.32727272727272727
    47: IndexNLJoin_Probe_const = 3.0
    48: IndexNLJoin_Probe_in_percentage = 1.5818181818181818
    49: IndexNLJoin_Probe_right_card = 3.0
    50: IndexNLJoin_Probe_out_percentage = 1.5636363636363635
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 104.0
    79: Sort_Scan_in_size = 8.0
    80: Sort_Scan_out_percentage = 1.0

## Rank 5: index_workload_100k_s2_c8220_339 (q_error = 326.9667)

- **actual** = 0.102958 s
- **pred (holdout)** = 33.663835 s
- **q_error** = 326.9667
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 339

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 2464.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 2464.0
    141: Aggregate_Scan_in_size = 10.0
    142: Aggregate_Scan_out_percentage = 0.00040584415584415587

#### Pipeline 1
- scan_size = 239344.0
- actual runtime = 0.102958 s
- pred runtime = 33.663835 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 2464.0
    3: TableScan_Scan_out_percentage = 0.010294805802526907
    5: TableScan_Scan_compare_percentage = 3.0
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 40.0
    138: Aggregate_Build_in_percentage = 0.010294805802526907


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.214906 s
- **q_error (zeroshot)** = 2.0873

(Zeroshot has 3 pipelines vs JH 2 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 239344.0
    27: Select_PassThrough_out_percentage = 241808.0

## Rank 6: index_workload_100k_s2_c8220_4163 (q_error = 292.5705)

- **actual** = 0.665496 s
- **pred (holdout)** = 194.704503 s
- **q_error** = 292.5705
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 4163

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 2283.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 2283.0
    141: Aggregate_Scan_in_size = 9.0
    142: Aggregate_Scan_out_percentage = 0.0004380201489268506

#### Pipeline 1
- scan_size = 545815.0
- actual runtime = 0.665484 s
- pred runtime = 194.704499 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 780.0
    3: TableScan_Scan_out_percentage = 0.0014290556324029204
    5: TableScan_Scan_compare_percentage = 2.0
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.0013942453028956698
    27: Select_PassThrough_out_percentage = 0.004182735908687009
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    123: NLJoin_Probe_const = 1.0
    124: NLJoin_Probe_in_percentage = 1.8321226056447697e-06
    125: NLJoin_Probe_right_card = 780.0
    126: NLJoin_Probe_out_percentage = 0.0013942453028956698
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 40.0
    138: Aggregate_Build_in_percentage = 0.004182735908687009

#### Pipeline 2
- scan_size = 1.0
- actual runtime = 0.000012 s
- pred runtime = 0.000005 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 761.0
    121: NLJoin_Build_out_size = 9.0
    122: NLJoin_Build_in_percentage = 1.0


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.375061 s
- **q_error (zeroshot)** = 1.7744

#### Zeroshot pipeline 0 features (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 3.0
    26: Select_PassThrough_in_percentage = 546576.0
    27: Select_PassThrough_out_percentage = 548878.0
    47: IndexNLJoin_Probe_const = 1.0
    48: IndexNLJoin_Probe_in_percentage = 780.0
    49: IndexNLJoin_Probe_right_card = 1.0
    50: IndexNLJoin_Probe_out_percentage = 761.0

#### Zeroshot pipeline 1 features (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    3: TableScan_Scan_out_percentage = 1.0
    5: TableScan_Scan_compare_percentage = 1.0

#### Zeroshot pipeline 2 features (non-zero):
    68: GroupBy_Scan_const = 1.0
    69: GroupBy_Scan_out_card = 1.0
    70: GroupBy_Scan_out_size = 40.0
    71: GroupBy_Scan_out_percentage = 1.0

## Rank 7: index_workload_100k_s2_c8220_1314 (q_error = 281.9535)

- **actual** = 0.152199 s
- **pred (holdout)** = 42.913034 s
- **q_error** = 281.9535
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1314

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 60.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 60.0
    141: Aggregate_Scan_in_size = 18.0
    142: Aggregate_Scan_out_percentage = 0.016666666666666666

#### Pipeline 1
- scan_size = 2683.0
- actual runtime = 0.114757 s
- pred runtime = 42.798285 s
Feature vector (non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.007454342154304882
    27: Select_PassThrough_out_percentage = 0.02236302646291465
    123: NLJoin_Probe_const = 4.0
    124: NLJoin_Probe_in_percentage = 3.738352590383898
    125: NLJoin_Probe_right_card = 200.0
    126: NLJoin_Probe_out_percentage = 0.07454342154304883
    127: MergeJoin_Probe_const = 1.0
    128: MergeJoin_Probe_in_percentage = 1.0
    129: MergeJoin_Probe_right_card = 1655.0
    130: MergeJoin_Probe_out_percentage = 0.007454342154304882
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 48.0
    138: Aggregate_Build_in_percentage = 0.02236302646291465

#### Pipeline 2
- scan_size = 1.0
- actual runtime = 0.000004 s
- pred runtime = 0.000007 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 60.0
    121: NLJoin_Build_out_size = 18.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 3
- scan_size = 25.0
- actual runtime = 0.000003 s
- pred runtime = 0.000151 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 25.0
    3: TableScan_Scan_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 60.0
    121: NLJoin_Build_out_size = 22.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 4
- scan_size = 10000.0
- actual runtime = 0.000874 s
- pred runtime = 0.038607 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 10000.0
    3: TableScan_Scan_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 60.0
    121: NLJoin_Build_out_size = 22.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 5
- scan_size = 4.0
- actual runtime = 0.000031 s
- pred runtime = 0.000032 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 20.0
    121: NLJoin_Build_out_size = 16.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 6
- scan_size = 1655.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 1655.0
    79: Sort_Scan_in_size = 12.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 20.0
    133: MergeJoin_Build_out_size = 16.0
    134: MergeJoin_Build_in_percentage = 1.6211480362537765

#### Pipeline 7
- scan_size = 2683.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 2684.0
    79: Sort_Scan_in_size = 4.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 20.0
    133: MergeJoin_Build_out_size = 16.0
    134: MergeJoin_Build_in_percentage = 1.0

#### Pipeline 8
- scan_size = 2508.0
- actual runtime = 0.017823 s
- pred runtime = 0.003786 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1655.0
    3: TableScan_Scan_out_percentage = 0.6598883572567783
    5: TableScan_Scan_compare_percentage = 1.0
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 1655.0
    74: Sort_Build_out_size = 12.0
    75: Sort_Build_in_percentage = 0.6598883572567783
    76: Sort_Build_out_percentage = 0.6598883572567783
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0

#### Pipeline 9
- scan_size = 86297.0
- actual runtime = 0.018707 s
- pred runtime = 0.072165 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 86297.0
    3: TableScan_Scan_out_percentage = 0.031101892302165778
    5: TableScan_Scan_compare_percentage = 1.0
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 2683.0
    74: Sort_Build_out_size = 4.0
    75: Sort_Build_in_percentage = 0.031101892302165778
    76: Sort_Build_out_percentage = 0.03109030441382667


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 1.006666 s
- **q_error (zeroshot)** = 6.6141

(Zeroshot has 9 pipelines vs JH 10 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.012084592145015106
    27: Select_PassThrough_out_percentage = 0.03625377643504532
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 1655.0
    45: HashJoin_Probe_right_percentage = 1.6211480362537765
    46: HashJoin_Probe_out_percentage = 0.012084592145015106
    47: IndexNLJoin_Probe_const = 4.0
    48: IndexNLJoin_Probe_in_percentage = 0.12084592145015106
    49: IndexNLJoin_Probe_right_card = 4.0
    50: IndexNLJoin_Probe_out_percentage = 0.12084592145015106
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 1655.0
    79: Sort_Scan_in_size = 12.0
    80: Sort_Scan_out_percentage = 1.0

## Rank 8: index_workload_100k_s2_c8220_1782 (q_error = 244.7905)

- **actual** = 0.143520 s
- **pred (holdout)** = 35.132336 s
- **q_error** = 244.7905
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 1782

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 2480.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 2480.0
    141: Aggregate_Scan_in_size = 9.0
    142: Aggregate_Scan_out_percentage = 0.0004032258064516129

#### Pipeline 1
- scan_size = 298723.0
- actual runtime = 0.143513 s
- pred runtime = 35.132332 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1746.0
    3: TableScan_Scan_out_percentage = 0.005844879704609287
    5: TableScan_Scan_compare_percentage = 2.0
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    123: NLJoin_Probe_const = 1.0
    124: NLJoin_Probe_in_percentage = 3.3475828777830968e-06
    125: NLJoin_Probe_right_card = 1746.0
    126: NLJoin_Probe_out_percentage = 0.00830200553690208
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 48.0
    138: Aggregate_Build_in_percentage = 0.00830200553690208

#### Pipeline 2
- scan_size = 1.0
- actual runtime = 0.000007 s
- pred runtime = 0.000004 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 2480.0
    121: NLJoin_Build_out_size = 9.0
    122: NLJoin_Build_in_percentage = 1.0


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.299049 s
- **q_error (zeroshot)** = 2.0837

(Zeroshot has 4 pipelines vs JH 3 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 298723.0
    27: Select_PassThrough_out_percentage = 300469.0
    47: IndexNLJoin_Probe_const = 1.0
    48: IndexNLJoin_Probe_in_percentage = 1746.0
    49: IndexNLJoin_Probe_right_card = 1.0
    50: IndexNLJoin_Probe_out_percentage = 2480.0

## Rank 9: index_workload_100k_s2_c8220_3294 (q_error = 221.3357)

- **actual** = 1.612256 s
- **pred (holdout)** = 356.849805 s
- **q_error** = 221.3357
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 3294

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 879.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 879.0
    141: Aggregate_Scan_in_size = 18.0
    142: Aggregate_Scan_out_percentage = 0.0011376564277588168

#### Pipeline 1
- scan_size = 19494.0
- actual runtime = 1.597118 s
- pred runtime = 356.804743 s
Feature vector (non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.022571047501795425
    27: Select_PassThrough_out_percentage = 0.045090797168359495
    123: NLJoin_Probe_const = 4.0
    124: NLJoin_Probe_in_percentage = 0.5132861393249205
    125: NLJoin_Probe_right_card = 2502.0
    126: NLJoin_Probe_out_percentage = 0.14312096029547555
    127: MergeJoin_Probe_const = 1.0
    128: MergeJoin_Probe_in_percentage = 1.0
    129: MergeJoin_Probe_right_card = 1078.0
    130: MergeJoin_Probe_out_percentage = 0.007797270955165692
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 40.0
    138: Aggregate_Build_in_percentage = 0.045090797168359495

#### Pipeline 2
- scan_size = 10000.0
- actual runtime = 0.000873 s
- pred runtime = 0.026026 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 10000.0
    3: TableScan_Scan_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 879.0
    121: NLJoin_Build_out_size = 18.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 3
- scan_size = 1.0
- actual runtime = 0.000011 s
- pred runtime = 0.000006 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 879.0
    121: NLJoin_Build_out_size = 20.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 4
- scan_size = 1.0
- actual runtime = 0.000090 s
- pred runtime = 0.000006 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 440.0
    121: NLJoin_Build_out_size = 20.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 5
- scan_size = 4.0
- actual runtime = 0.000026 s
- pred runtime = 0.000021 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    119: NLJoin_Build_const = 1.0
    120: NLJoin_Build_out_card = 592.0
    121: NLJoin_Build_out_size = 12.0
    122: NLJoin_Build_in_percentage = 1.0

#### Pipeline 6
- scan_size = 1078.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 1228.0
    79: Sort_Scan_in_size = 8.0
    80: Sort_Scan_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 152.0
    133: MergeJoin_Build_out_size = 8.0
    134: MergeJoin_Build_in_percentage = 18.083487940630796

#### Pipeline 7
- scan_size = 19494.0
- actual runtime = 0.003100 s
- pred runtime = 0.004556 s
Feature vector (non-zero):
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    131: MergeJoin_Build_const = 1.0
    132: MergeJoin_Build_out_card = 152.0
    133: MergeJoin_Build_out_size = 8.0
    134: MergeJoin_Build_in_percentage = 1.0

#### Pipeline 8
- scan_size = 1525.0
- actual runtime = 0.011038 s
- pred runtime = 0.014447 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1228.0
    3: TableScan_Scan_out_percentage = 0.8052459016393443
    5: TableScan_Scan_compare_percentage = 2.0
    72: Sort_Build_const = 1.0
    73: Sort_Build_out_card = 1078.0
    74: Sort_Build_out_size = 8.0
    75: Sort_Build_in_percentage = 0.8052459016393443
    76: Sort_Build_out_percentage = 0.7068852459016394
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 1.216723 s
- **q_error (zeroshot)** = 1.3251

(Zeroshot has 8 pipelines vs JH 9 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    25: Select_PassThrough_const = 1.0
    26: Select_PassThrough_in_percentage = 0.40816326530612246
    27: Select_PassThrough_out_percentage = 0.8153988868274582
    43: HashJoin_Probe_const = 1.0
    44: HashJoin_Probe_in_card = 1078.0
    45: HashJoin_Probe_right_percentage = 18.083487940630796
    46: HashJoin_Probe_out_percentage = 0.14100185528756956
    47: IndexNLJoin_Probe_const = 4.0
    48: IndexNLJoin_Probe_in_percentage = 2.320964749536178
    49: IndexNLJoin_Probe_right_card = 4.0
    50: IndexNLJoin_Probe_out_percentage = 2.588126159554731
    77: Sort_Scan_const = 1.0
    78: Sort_Scan_in_card = 1228.0
    79: Sort_Scan_in_size = 8.0
    80: Sort_Scan_out_percentage = 1.0

## Rank 10: index_workload_100k_s2_c8220_3151 (q_error = 145.7236)

- **actual** = 0.750101 s
- **pred (holdout)** = 109.307387 s
- **q_error** = 145.7236
- **source** = `/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/index_workload_100k_s2_c8220.json` plan_index = 3151

### Per-pipeline (JH holdout)

#### Pipeline 0
- scan_size = 2480.0
- actual runtime = 0.000000 s
- pred runtime = 0.000000 s
Feature vector (non-zero):
    139: Aggregate_Scan_const = 1.0
    140: Aggregate_Scan_in_card = 2480.0
    141: Aggregate_Scan_in_size = 8.0
    142: Aggregate_Scan_out_percentage = 0.0004032258064516129

#### Pipeline 1
- scan_size = 857324.0
- actual runtime = 0.750101 s
- pred runtime = 109.307387 s
Feature vector (non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 2480.0
    3: TableScan_Scan_out_percentage = 0.002892722004749663
    5: TableScan_Scan_compare_percentage = 4.0
    110: IdxScan_Probe_const = 1.0
    111: IdxScan_Probe_out_percentage = 1.0
    135: Aggregate_Build_const = 1.0
    136: Aggregate_Build_out_card = 1.0
    137: Aggregate_Build_out_size = 40.0
    138: Aggregate_Build_in_percentage = 0.002892722004749663


### Zeroshot comparison (same plan, zeroshot pipeline)

- **pred (zeroshot)** = 0.260801 s
- **q_error (zeroshot)** = 2.8761

(Zeroshot has 3 pipelines vs JH 2 — pipeline count differs.)
Zeroshot feature vector (first row, non-zero):
    0: TableScan_Scan_const = 1.0
    1: TableScan_Scan_in_card = 1.0
    10: TableScan_Scan_empty_output = 1.0
    25: Select_PassThrough_const = 2.0
    26: Select_PassThrough_in_percentage = 857324.0
    27: Select_PassThrough_out_percentage = 859804.0
