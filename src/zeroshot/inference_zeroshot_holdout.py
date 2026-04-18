"""
Run inference on a specified holdout benchmark using an existing zero-shot T3 model.

Evaluates only JSONs under the selected holdout benchmark folder (same split logic as
training_zeroshot_tpch_holdout) and writes one summary line to inference.txt in the
same format as the holdout test-set summary.

Usage (from T3 project root):
  python -m src.zeroshot.inference_zeroshot_holdout
  python -m src.zeroshot.inference_zeroshot_holdout --holdout tpc_h --model model_zero_tpch_holdout.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb

from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.pg_features import PgFeatureMapper
from src.zeroshot.training_zeroshot_tpch_holdout import (
    DEFAULT_DATA_DIR,
    HOLDOUT_BENCHMARK,
    collect_all_zeroshot_jsons,
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)
from src.zeroshot.training_zeroshot_tpch_holdout_ql import estimate_runtime_query_level

DEFAULT_MODEL_PATH = "model_zero_tpch_holdout.txt"
DEFAULT_OUTPUT_FILE = "inference.txt"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run holdout inference on zero-shot parsed plans using an existing model."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(DEFAULT_DATA_DIR),
        help=f"Root directory containing zero-shot JSON files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(DEFAULT_MODEL_PATH),
        help=f"Path to model file (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--holdout",
        type=str,
        default=HOLDOUT_BENCHMARK,
        help=f"Benchmark folder name used as inference set (default: {HOLDOUT_BENCHMARK})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(DEFAULT_OUTPUT_FILE),
        help=f"Output file for inference summary (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--use-estimated-card",
        action="store_true",
        help="Use estimated cardinalities (est_card) instead of actual; same feature names.",
    )
    parser.add_argument(
        "--query-level",
        action="store_true",
        help=(
            "Use query-level inference: sum all per-pipeline feature vectors into one "
            "vector per query and predict total runtime directly. "
            "Must match the --query-level flag used during training."
        ),
    )
    args = parser.parse_args()

    use_actual_card = not args.use_estimated_card

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(data_dir)
    if not all_json_paths:
        print(f"No .json files under {data_dir}")
        sys.exit(1)

    _, test_paths = split_train_test_by_holdout(all_json_paths, holdout_name=args.holdout)
    if not test_paths:
        print(f"Error: no inference files (no path contains '{args.holdout}').")
        sys.exit(1)

    model_path = args.model if args.model.is_absolute() else _repo / args.model
    if not model_path.is_file():
        print(f"Error: model file not found: {model_path}")
        sys.exit(1)

    queries = load_benchmarked_queries_from_zeroshot(
        test_paths, use_actual_card=use_actual_card
    )
    if not queries:
        print("Error: no inference queries could be loaded.")
        sys.exit(1)

    feature_mapper = PgFeatureMapper()
    booster = lgb.Booster(model_file=str(model_path))
    model = PerTupleTreeModel(booster, feature_mapper=feature_mapper)

    print(f"Mode: {'query-level' if args.query_level else 'per-pipeline'}")

    errors: list[float] = []
    for b in queries:
        if args.query_level:
            pred = estimate_runtime_query_level(booster, b, feature_mapper)
        else:
            pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        err = q_error(actual, pred)
        errors.append(err)
        print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")

    summary = (
        f"Test set ({args.holdout}, {len(queries)} queries): "
        f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p90={np.percentile(errors, 90):.4f} "
        f"model={model_path.name}"
    )
    print(summary)

    out_path = args.out if args.out.is_absolute() else _repo / args.out
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(f"Inference summary appended to {out_path}")


if __name__ == "__main__":
    main()
