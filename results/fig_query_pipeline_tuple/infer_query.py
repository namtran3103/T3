"""
Query-level inference for the query/pipeline/tuple comparison figure.

Uses act models from results/models/query-level/act/ with actual cardinalities.
Each holdout is evaluated with the model trained leaving that holdout out.
Metrics (avg, p50, p90 q-error) are computed over ALL queries accumulated
across every holdout, not per-database.
Results are appended to query.txt in this directory.
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
MODEL_DIR = SCRIPT_DIR.parent / "models" / "query-level" / "act"
OUT_FILE = SCRIPT_DIR / "query.txt"


def main() -> None:
    data_dir = Path(DEFAULT_DATA_DIR).resolve()
    if not data_dir.is_dir():
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(data_dir)
    if not all_json_paths:
        print(f"No .json files under {data_dir}")
        sys.exit(1)

    print(f"Found {len(all_json_paths)} JSON files")

    model_files = sorted(
        p for p in MODEL_DIR.glob("*.txt") if p.stem != "0_results"
    )
    if not model_files:
        print(f"No model files found in {MODEL_DIR}")
        sys.exit(1)

    feature_mapper = PgFeatureMapper()
    all_errors: list[float] = []
    total_queries = 0

    for model_path in model_files:
        holdout = model_path.stem
        _, test_paths = split_train_test_by_holdout(all_json_paths, holdout_name=holdout)
        if not test_paths:
            print(f"  [{holdout}] No test paths found, skipping.")
            continue

        queries = load_benchmarked_queries_from_zeroshot(test_paths, use_actual_card=True)
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
        print("No errors collected.")
        sys.exit(1)

    avg = float(np.mean(all_errors))
    p50 = float(np.median(all_errors))
    p90 = float(np.percentile(all_errors, 90))

    summary = (
        f"query-level (act): {total_queries} queries across {len(model_files)} holdouts | "
        f"q-error avg={avg:.4f} p50={p50:.4f} p90={p90:.4f}"
    )
    print(f"\n{summary}")

    with open(OUT_FILE, "a", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(f"Appended to {OUT_FILE}")


if __name__ == "__main__":
    main()
