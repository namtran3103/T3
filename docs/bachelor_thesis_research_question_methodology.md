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

## Full Thesis Structure (Recommended)

This chapter plan fits your topic very well and is scientifically consistent with the research question.

## 1. Introduction

- Motivation: fast and accurate runtime prediction for query optimization/scheduling.
- Problem statement: transfer T3 from Umbra to PostgreSQL parsed plans.
- Research question and contributions.

## 2. Theoretical Background

Use your intended sections, with one adjustment on scope:

- **Decision Trees:** regression trees, gradient boosting, why trees are suitable for low-latency inference.
- **PostgreSQL:** physical plans, operators, cardinalities/costs, relevant `EXPLAIN`/parsed plan signals.
- **Umbra:** operator/pipeline model and why T3 was designed in that context.
- **T3 (from `t3.pdf`):** pipeline-based representation, tuple-centric target transformation, compiled decision trees.
- **Related Work:** zero-shot cost models (`3551793.3551799.pdf`) and other learned runtime prediction work.

Important placement note:
- Introduce **zero-shot parsed plans and runtime filtering** in your **Data/Method** chapter (not only in Related Work), because this is part of your experimental pipeline and must be reproducible.

## 3. Methodology and Implementation

- Data source and preprocessing (`parsed_plans`, filtering rules, split logic).
- System A (direct T3 transfer baseline: Umbra-style features).
- System B (adapted T3 with PostgreSQL-native features).
- Controlled training/evaluation protocol.

## 4. Experimental Setup

- Hardware/software environment.
- Metrics (q-error p50/p90/avg/max).
- Holdout setup and cardinality variants (actual vs estimated, where applicable).

## 5. Results

- Baseline transfer results.
- PG-native feature adaptation results.
- Ablations/robustness analyses.

## 6. Discussion

- Interpretation of where transfer works/fails.
- Comparison to prior work (T3 paper, Zero-Shot, JOBComplex implementation where comparable).
- Threats to validity and limits of comparability.

## 7. Conclusion and Future Work

- Directly answer the RQ.
- Summarize methodological and empirical contributions.

---

## Comparison Strategy to Prior Work

Your plan to compare against `JOBComplex.pdf` and Zero-Shot holdout results is good, with one scientific caution:

- **Within-work first:** Primary claim should be baseline vs adapted model under identical conditions in your codebase.
- **Cross-paper second:** External comparisons should be clearly labeled as **indicative**, because data generation, execution engines, and evaluation protocols may differ.
- **JOB-full comparison:** Good fit for discussion, especially since your results include JOB-full evaluation; state differences in setup explicitly.
- **Holdout comparison with Zero-Shot:** Reasonable and valuable, especially if using the same parsed-plan source and similar split logic.

## Where to Mention `JOBComplex.pdf` (Concrete Placement)

- **Theoretical Background -> T3 section (short mention):**
  - 2-4 sentences that position `JOBComplex.pdf` as a PostgreSQL-oriented T3-related implementation/evaluation on JOB.
  - Goal: context and motivation, not detailed numerical comparison.

- **Related Work section (main literature positioning):**
  - Summarize their setup, task, and key metric(s).
  - Clearly distinguish overlap and differences to your work (data source, feature encoding, splits, evaluation scope).
  - This is the main place where the reader learns why comparison is useful but limited.

- **Results/Discussion -> External Comparison subsection (quantitative interpretation):**
  - Compare your JOB-full results to their reported values.
  - Explicitly add a "comparability caveat" paragraph (different protocols/engines/features/hardware).
  - Use wording like "indicative comparison" rather than "direct benchmark winner."

- **Methodology (one-line justification only):**
  - Briefly state that JOB-full is included partly to enable discussion against prior JOB-focused T3-related work.

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
- Define inclusion/exclusion from code (e.g., runtime availability checks, conversion failures, skipped plans).
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
- For the primary system comparison, keep all conditions fixed except feature representation.
- Report exact training settings and seeds to ensure reproducibility.
- Primary comparison protocol: compare both systems on actual-cardinality runs only.
- Cardinality robustness is treated as a separate ablation (estimated-cardinality runs where implemented, currently on the PG-native system).

## 7. Evaluation Metrics and Analyses

- Primary metric: q-error distribution (`p50`, `p90`, `avg`, `max`).
- Secondary analysis: error stratification by benchmark/query type if available.
- Transfer evaluation logic:
  - Step 1: show baseline transfer works (non-trivial predictive quality).
  - Step 2: show dedicated PG features improve predictive quality.
  - Step 3: separately analyze cardinality robustness on the system variant where estimated-cardinality experiments are available.

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
- Add external comparison subsection:
  - comparison to T3-for-Postgres/JOBComplex results,
  - comparison to Zero-Shot holdout literature values,
  - explicit statement of comparability limits.

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

