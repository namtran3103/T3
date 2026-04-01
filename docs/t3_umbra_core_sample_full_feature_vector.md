# T3 Umbra Core: Sample Full Feature Vector

This document gives one **sample full feature vector** based only on the core files in `src/`.

- Vector layout source: `src/features.py` (`QualifiedFeature.enumerate_features`)
- Operator/stage semantics source: `src/operator_stages.py`
- Cardinality/expression feature source: `src/query_plan.py`

## Sample scenario

A single `TableScan` in `Scan` stage contributes to the vector (all other operator-stage slots stay `0.0` for this sample).

Chosen sample values:

- `TableScan_Scan_const = 1.0`
- `TableScan_Scan_in_card = 100000.0`
- `TableScan_Scan_in_size = 64.0`
- `TableScan_Scan_out_percentage = 0.125`
- `TableScan_Scan_like_percentage = 0.02`
- `TableScan_Scan_compare_percentage = 0.15`
- `TableScan_Scan_in_expression_percentage = 0.0`
- `TableScan_Scan_between_percentage = 0.03`
- `TableScan_Scan_or_exp_percentage = 0.01`
- `TableScan_Scan_starts_with_percentage = 0.0`
- `TableScan_Scan_empty_output = 0.0`

## Full dense vector (110 dims)

Format: `index<TAB>feature_name<TAB>value`

```text
0	TableScan_Scan_const	1.0
1	TableScan_Scan_in_card	100000.0
2	TableScan_Scan_in_size	64.0
3	TableScan_Scan_out_percentage	0.125
4	TableScan_Scan_like_percentage	0.02
5	TableScan_Scan_compare_percentage	0.15
6	TableScan_Scan_in_expression_percentage	0.0
7	TableScan_Scan_between_percentage	0.03
8	TableScan_Scan_or_exp_percentage	0.01
9	TableScan_Scan_starts_with_percentage	0.0
10	TableScan_Scan_empty_output	0.0
11	InlineTable_Scan_const	0.0
12	InlineTable_Scan_in_card	0.0
13	InlineTable_Scan_in_size	0.0
14	InlineTable_Scan_out_percentage	0.0
15	PipelineBreakerScan_Scan_const	0.0
16	PipelineBreakerScan_Scan_in_card	0.0
17	PipelineBreakerScan_Scan_in_size	0.0
18	PipelineBreakerScan_Scan_out_percentage	0.0
19	Temp_Build_const	0.0
20	Temp_Build_out_card	0.0
21	Temp_Build_out_size	0.0
22	Temp_Build_in_percentage	0.0
23	EarlyExecution_Scan_const	0.0
24	EarlyExecution_Scan_out_percentage	0.0
25	Select_PassThrough_const	0.0
26	Select_PassThrough_in_percentage	0.0
27	Select_PassThrough_out_percentage	0.0
28	Map_PassThrough_const	0.0
29	Map_PassThrough_in_percentage	0.0
30	Map_PassThrough_out_percentage	0.0
31	MultiWayJoin_Build_const	0.0
32	MultiWayJoin_Build_out_card	0.0
33	MultiWayJoin_Build_out_size	0.0
34	MultiWayJoin_Build_in_percentage	0.0
35	MultiWayJoin_Scan_const	0.0
36	MultiWayJoin_Scan_in_card	0.0
37	MultiWayJoin_Scan_in_size	0.0
38	MultiWayJoin_Scan_out_percentage	0.0
39	HashJoin_Build_const	0.0
40	HashJoin_Build_out_card	0.0
41	HashJoin_Build_out_size	0.0
42	HashJoin_Build_in_percentage	0.0
43	HashJoin_Probe_const	0.0
44	HashJoin_Probe_in_card	0.0
45	HashJoin_Probe_right_percentage	0.0
46	HashJoin_Probe_out_percentage	0.0
47	IndexNLJoin_Probe_const	0.0
48	IndexNLJoin_Probe_in_percentage	0.0
49	IndexNLJoin_Probe_right_card	0.0
50	IndexNLJoin_Probe_out_percentage	0.0
51	GroupJoin_Build_const	0.0
52	GroupJoin_Build_out_card	0.0
53	GroupJoin_Build_out_size	0.0
54	GroupJoin_Build_in_percentage	0.0
55	GroupJoin_Probe_const	0.0
56	GroupJoin_Probe_out_card	0.0
57	GroupJoin_Probe_out_size	0.0
58	GroupJoin_Probe_right_percentage	0.0
59	GroupJoin_Probe_out_percentage	0.0
60	GroupJoin_Scan_const	0.0
61	GroupJoin_Scan_in_card	0.0
62	GroupJoin_Scan_in_size	0.0
63	GroupJoin_Scan_out_percentage	0.0
64	GroupBy_Build_const	0.0
65	GroupBy_Build_out_card	0.0
66	GroupBy_Build_out_size	0.0
67	GroupBy_Build_in_percentage	0.0
68	GroupBy_Scan_const	0.0
69	GroupBy_Scan_out_card	0.0
70	GroupBy_Scan_out_size	0.0
71	GroupBy_Scan_out_percentage	0.0
72	Sort_Build_const	0.0
73	Sort_Build_out_card	0.0
74	Sort_Build_out_size	0.0
75	Sort_Build_in_percentage	0.0
76	Sort_Build_out_percentage	0.0
77	Sort_Scan_const	0.0
78	Sort_Scan_in_card	0.0
79	Sort_Scan_in_size	0.0
80	Sort_Scan_out_percentage	0.0
81	SetOperation_Build_const	0.0
82	SetOperation_Build_out_card	0.0
83	SetOperation_Build_out_size	0.0
84	SetOperation_Build_in_percentage	0.0
85	SetOperation_Scan_const	0.0
86	SetOperation_Scan_in_card	0.0
87	SetOperation_Scan_in_size	0.0
88	SetOperation_Scan_out_percentage	0.0
89	SetOperation_PassThrough_const	0.0
90	Window_Build_const	0.0
91	Window_Build_out_card	0.0
92	Window_Build_out_size	0.0
93	Window_Build_in_percentage	0.0
94	Window_Scan_const	0.0
95	Window_Scan_in_card	0.0
96	Window_Scan_in_size	0.0
97	Window_Scan_out_percentage	0.0
98	FileOutput_Build_const	0.0
99	FileOutput_Build_out_card	0.0
100	FileOutput_Build_out_size	0.0
101	FileOutput_Build_in_percentage	0.0
102	CsvWriter_Build_const	0.0
103	CsvWriter_Build_out_card	0.0
104	CsvWriter_Build_out_size	0.0
105	CsvWriter_Build_in_percentage	0.0
106	AssertSingle_PassThrough_const	0.0
107	AssertSingle_PassThrough_in_percentage	0.0
108	EarlyProbe_PassThrough_const	0.0
109	EarlyProbe_PassThrough_out_percentage	0.0
```

