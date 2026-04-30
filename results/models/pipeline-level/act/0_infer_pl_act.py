"""
Pipeline-level inference with actual cardinalities for all models in this directory.

Evaluates each <holdout>.txt model against its own holdout split and appends one
summary line per holdout to 0_results.txt.

Usage (from T3 project root or this directory):
  python results/models/pipeline-level/act/0_infer_pl_act.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_script_dir = Path(__file__).resolve().parent
_repo = _script_dir.parent.parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import lightgbm as lgb

from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.pg_features import PgFeatureMapper
from src.zeroshot.training_zeroshot_tpch_holdout import (
    DEFAULT_DATA_DIR,
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons

RESULTS_FILE = _script_dir / "0_results.txt"
USE_ACTUAL_CARD = True


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
        p for p in _script_dir.glob("*.txt") if p.stem != "0_results"
    )
    if not model_files:
        print(f"No model files found in {_script_dir}")
        sys.exit(1)

    feature_mapper = PgFeatureMapper()

    for model_path in model_files:
        holdout = model_path.stem
        print(f"\n==> Inferring: {holdout}")

        _, test_paths = split_train_test_by_holdout(all_json_paths, holdout_name=holdout)
        if not test_paths:
            print(f"  No test paths found for {holdout}, skipping.")
            continue

        queries = load_benchmarked_queries_from_zeroshot(test_paths, use_actual_card=USE_ACTUAL_CARD)
        if not queries:
            print(f"  No queries loaded for {holdout}, skipping.")
            continue

        booster = lgb.Booster(model_file=str(model_path))
        model = PerTupleTreeModel(booster, feature_mapper=feature_mapper)

        errors: list[float] = []
        for b in queries:
            pred = model.estimate_runtime(b)
            actual = b.get_total_runtime()
            err = q_error(actual, pred)
            errors.append(err)
            print(f"  {b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")

        summary = (
            f"Test set ({holdout}, {len(errors)} queries): "
            f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} "
            f"p90={np.percentile(errors, 90):.4f} model={model_path.name}"
        )
        print(f"  {summary}")
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(summary + "\n")

    print(f"\nDone. Results appended to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
