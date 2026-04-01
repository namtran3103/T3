# Bachelor Thesis: Research Question and Methodology Structure

## Context and Framing

This thesis studies a **transfer problem**: taking the T3 approach from the paper (pipeline-based representation, tuple-centric prediction target, gradient-boosted trees) and adapting it from Umbra to PostgreSQL parsed plans.  
Your implementation uses parsed plans from `zero-shot-data/runs/parsed_plans` and realizes this transfer in two stages:

1. **Transfer baseline:** convert parsed plans to T3-compatible plan/pipeline structures and reuse the original Umbra-oriented `FeatureMapper` (`src/features.py`).
2. **Adapted variant:** keep the same prediction pipeline but replace feature encoding with a PostgreSQL-native representation via `PgFeatureMapper` (`src/pg_features.py`).

This creates a clean scientific narrative: first show transfer feasibility, then show which adaptation choices improve predictive quality.

---

## Research Question

### Main Research Question

**How can the T3 runtime prediction approach be transferred from Umbra to PostgreSQL parsed plans, and how accurately does the resulting model predict query runtimes?**

### Sub-Questions

1. **Feasibility of transfer:**  
   Which components of T3 can be reused unchanged, and which components require adaptation for PostgreSQL parsed plans?
2. **Baseline quality after transfer:**  
   How accurate is runtime prediction when the transferred system uses the original Umbra-style feature encoding?
3. **Effect of PG-native adaptation:**  
   How much does a dedicated PostgreSQL feature vector improve accuracy compared with the transfer baseline?
4. **Robustness conditions:**  
   How sensitive are both variants to cardinality source (actual vs estimated) and where do major errors occur (p50 vs p90/max)?

---

## Hypotheses

- **H1 (Transfer feasibility):** Core T3 mechanics (pipeline decomposition, tuple-centric target learning, boosted trees) transfer to PostgreSQL parsed plans with only interface-level conversion.
- **H2 (Need for adaptation):** A pure transfer baseline with Umbra-style feature encoding is functional but suboptimal due to representation mismatch.
- **H3 (Accuracy gain):** PostgreSQL-native feature encoding improves both central and tail q-error metrics over the transfer baseline.
- **H4 (Cardinality sensitivity):** Estimated cardinalities degrade both variants, but the PG-native encoding remains comparatively more stable.

---

## Methodology Structure (Chapter-Level)

## 1. Problem Statement and Scientific Scope

- Define the transfer objective from T3 (Umbra context) to PostgreSQL parsed plans.
- Define prediction target: query runtime as sum of predicted pipeline runtimes from per-tuple predictions.
- Define system boundary: offline learning-based prediction, no concurrent workload modeling, no optimizer integration claims unless tested.

## 2. Source Model and Transfer Design

- Summarize the T3 concepts adopted from the paper: pipeline-level modeling, tuple-centric transformed target, boosted trees.
- Explicitly map each concept to your implementation artifacts.
- State transfer principle: preserve T3 learning logic, modify only data representation and feature extraction where necessary.

## 3. Data and Preprocessing

- Describe dataset source: parsed plans under `zero-shot-data/runs/parsed_plans`.
- Define analysis unit: each element in `parsed_plans`.
- Define inclusion/exclusion from code (e.g., runtime availability checks, conversion failures).
- Define split strategy (benchmark holdout in `training_zeroshot_tpch_holdout.py` and related scripts).

## 4. System A: Direct T3 Transfer Baseline

- Describe conversion path in `src/zeroshot/zeroshot_to_t3.py`:
  - PostgreSQL parsed plan -> T3/Umbra-style plan structure,
  - pipeline assignment and operator mapping assumptions,
  - construction of `QueryPlan`.
- State clearly: features are extracted with unchanged `FeatureMapper` (`src/features.py`).
- Position this as the core answer to "can T3 be transferred at all?"

## 5. System B: T3 Transfer with PostgreSQL-Native Features

- Describe motivation for adaptation: reduce semantic mismatch caused by Umbra-oriented feature assumptions.
- Describe `PgFeatureMapper` in `src/pg_features.py` and feature families:
  - operator/cardinality/cost/width/parallelism signals,
  - filter-structure information,
  - operator-level aggregated signals.
- Document leakage-control decisions (e.g., avoid using observed timing fields as input features).

## 6. Learning Setup and Controlled Comparison Protocol

- Use identical model family and training process for both systems (LightGBM-based tuple-centric pipeline model).
- Keep all conditions fixed except feature representation.
- Report exact training settings and seeds to ensure reproducibility.
- Include both actual-cardinality and estimated-cardinality variants where implemented.

## 7. Evaluation Metrics and Analyses

- Primary metric: q-error distribution (`p50`, `p90`, `avg`, `max`).
- Secondary analysis: error stratification by benchmark/query type if available.
- Transfer evaluation logic:
  - Step 1: show baseline transfer works (non-trivial predictive quality).
  - Step 2: show dedicated PG features improve predictive quality.
  - Step 3: analyze robustness under estimated cardinalities.

## 8. Threats to Validity

- **Internal validity:** heuristics in operator mapping and pipeline assignment.
- **Construct validity:** runtime labels may include benchmark noise; q-error has known sensitivity to outliers.
- **External validity:** findings are tied to available parsed-plan benchmarks and hardware/software setup.
- **Conclusion validity:** control seed/split effects and report confidence/variation where feasible.

## 9. Result Reporting and Discussion

- Present two clear result blocks:
  - Transfer baseline performance (answers feasibility and baseline accuracy).
  - Adapted PG-feature performance and delta to baseline.
- Interpret improvements in terms of representation quality, not only raw numbers.
- Relate findings back to T3 transferability claims.

## 10. Conclusion and Future Work

- Conclude with a direct answer to the main RQ (transfer method + achieved accuracy).
- Separate contributions into:
  - engineering contribution (T3 transfer pipeline for PostgreSQL parsed plans),
  - empirical contribution (controlled comparison of feature representations).
- Future work: improved cardinality inputs, broader workloads, and optional latency-focused model deployment analysis.

---

## Final Structure Check

Your project structure is now aligned with the new research question and scientifically coherent:

1. Transfer T3 to PostgreSQL parsed plans (method).
2. Measure baseline predictive performance after transfer (feasibility + quality).
3. Improve representation with PG-native features and quantify gains (controlled comparison).

This is exactly the right structure for your bachelor thesis topic.

