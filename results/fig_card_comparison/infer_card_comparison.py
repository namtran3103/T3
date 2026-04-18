"""
Query-level inference for the cardinality comparison figure (fig_card_comparison).

Three scenarios, each using per-holdout models from results/models/query-level/:
  act_act : act model  + actual cardinalities  → act_act.txt
  act_est : act model  + estimated cardinalities → act_est.txt
  est_est : est model  + estimated cardinalities → est_est.txt

Metrics (p50, p90, avg q-error) are computed over ALL queries accumulated across
every holdout, not per-database.  Each holdout is evaluated with the model that
was trained leaving that holdout out.
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb

from src.metrics import q_error
from src.pg_features import PgFeatureMapper
from src.zeroshot.training_zeroshot_tpch_holdout import (
    DEFAULT_DATA_DIR,
    collect_all_zeroshot_jsons,
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)
from src.zeroshot.training_zeroshot_tpch_holdout_ql import estimate_runtime_query_level

SCRIPT_DIR = Path(__file__).resolve().parent
ACT_MODEL_DIR = SCRIPT_DIR.parent / "models" / "query-level" / "act"
EST_MODEL_DIR = SCRIPT_DIR.parent / "models" / "query-level" / "est"

SCENARIOS: list[tuple[str, Path, bool]] = [
    # (output_file_stem, model_dir, use_actual_card)
    ("act_act", ACT_MODEL_DIR, True),
    ("act_est", ACT_MODEL_DIR, False),
    ("est_est", EST_MODEL_DIR, False),
]


def run_scenario(
    label: str,
    model_dir: Path,
    use_actual_card: bool,
    data_dir: Path,
    all_json_paths: list[Path],
    feature_mapper: PgFeatureMapper,
) -> None:
    out_path = SCRIPT_DIR / f"{label}.txt"
    print(f"\n{'='*60}")
    print(f"Scenario: {label}  (model_dir={model_dir.name}, actual_card={use_actual_card})")
    print(f"{'='*60}")

    model_files = sorted(
        p for p in model_dir.glob("*.txt") if p.stem != "0_results"
    )
    if not model_files:
        print(f"  No model files found in {model_dir}")
        return

    all_errors: list[float] = []
    total_queries = 0

    for model_path in model_files:
        holdout = model_path.stem
        _, test_paths = split_train_test_by_holdout(all_json_paths, holdout_name=holdout)
        if not test_paths:
            print(f"  [{holdout}] No test paths found, skipping.")
            continue

        queries = load_benchmarked_queries_from_zeroshot(
            test_paths, use_actual_card=use_actual_card
        )
        if not queries:
            print(f"  [{holdout}] No queries loaded, skipping.")
            continue

        booster = lgb.Booster(model_file=str(model_path))

        errors_for_holdout: list[float] = []
        for b in queries:
            pred = estimate_runtime_query_level(booster, b, feature_mapper)
            actual = b.get_total_runtime()
            err = q_error(actual, pred)
            errors_for_holdout.append(err)

        all_errors.extend(errors_for_holdout)
        total_queries += len(queries)
        print(
            f"  [{holdout:20s}] {len(queries):4d} queries  "
            f"local p50={np.median(errors_for_holdout):.4f}  "
            f"avg={np.mean(errors_for_holdout):.4f}"
        )

    if not all_errors:
        print(f"  No errors collected for scenario {label}.")
        return

    avg = float(np.mean(all_errors))
    p50 = float(np.median(all_errors))
    p90 = float(np.percentile(all_errors, 90))

    summary = (
        f"{label}: {total_queries} queries across {len(model_files)} holdouts | "
        f"q-error avg={avg:.4f} p50={p50:.4f} p90={p90:.4f}"
    )
    print(f"\n  {summary}")

    with open(out_path, "a", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(f"  Written to {out_path}")


def main() -> None:
    data_dir = Path(DEFAULT_DATA_DIR).resolve()
    if not data_dir.is_dir():
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(data_dir)
    if not all_json_paths:
        print(f"No .json files under {data_dir}")
        sys.exit(1)

    print(f"Found {len(all_json_paths)} JSON files in {data_dir}")

    feature_mapper = PgFeatureMapper()

    for label, model_dir, use_actual_card in SCENARIOS:
        run_scenario(
            label=label,
            model_dir=model_dir,
            use_actual_card=use_actual_card,
            data_dir=data_dir,
            all_json_paths=all_json_paths,
            feature_mapper=feature_mapper,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
