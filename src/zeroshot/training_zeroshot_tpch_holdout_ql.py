"""
Train a query-level T3 variant on zero-shot parsed plans with one benchmark held out.

Instead of one training row per pipeline, each query contributes a single feature vector
formed by summing all its per-pipeline feature vectors.  The label is the total query
runtime.  This is the "single feature vector per query" variant described in the paper:

    "We simply use the sum of all per pipeline feature vectors."

Same holdout split and CLI interface as training_zeroshot_tpch_holdout.

If the output file already exists, saves to _v1, _v2, ... (next free number).  Appends
test summary to holdout.txt (append, no overwrite).

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_tpch_holdout_ql
  python -m src.zeroshot.training_zeroshot_tpch_holdout_ql --holdout tpc_h --out model_zero_tpch_holdout_ql.txt
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
from sklearn.model_selection import train_test_split

from src.metrics import q_error
from src.pg_features import PgFeatureMapper
from src.optimizer import BenchmarkedQuery
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons
from src.zeroshot.training_zeroshot_tpch_holdout import (
    SEED,
    HOLDOUT_BENCHMARK,
    DEFAULT_DATA_DIR,
    next_available_model_path,
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)

DEFAULT_MODEL_PATH_QL = "model_zero_tpch_holdout_ql.txt"


def aggregate_query_level_data(
    queries: list[BenchmarkedQuery],
    feature_mapper: PgFeatureMapper,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build query-level training data: sum all per-pipeline feature vectors for each query
    into a single vector; label = total query runtime.  One row per query.
    """
    x_vectors: list[np.ndarray] = []
    y_values: list[float] = []
    for query in queries:
        x = query.get_feature_matrix(feature_mapper)
        if x.ndim < 2 or x.shape[0] == 0:
            continue
        x_sum = np.sum(x, axis=0)
        if not np.any(x_sum != 0):
            continue
        x_vectors.append(x_sum)
        y_values.append(query.get_total_runtime())
    if not x_vectors:
        raise ValueError(
            "No query rows with non-zero features. Check zero-shot plans and conversions."
        )
    return np.vstack(x_vectors), np.array(y_values)


def estimate_runtime_query_level(
    booster: lgb.Booster,
    query: BenchmarkedQuery,
    feature_mapper: PgFeatureMapper,
) -> float:
    """
    Predict total query runtime using the summed pipeline feature vector.
    Reverses the -log label transform applied during query-level training.
    """
    x = query.get_feature_matrix(feature_mapper)
    x_sum = np.sum(x, axis=0, keepdims=True)
    raw = booster.predict(x_sum).flatten()[0]
    return max(1e-6, float(np.exp(-raw)))


def train_query_level_lightgbm(
    queries: list[BenchmarkedQuery],
    seed: int = SEED,
    num_trees: int = 200,
) -> lgb.Booster:
    """
    Train LightGBM on query-level feature rows (one summed vector per query).

    Labels are -log(total_query_runtime).  At inference, apply exp(-raw_pred)
    to recover the predicted runtime.  num_trees: boosting rounds.
    """
    feature_mapper = PgFeatureMapper()
    x, y = aggregate_query_level_data(queries, feature_mapper)
    y = np.maximum(y, 1e-15)
    y = -np.log(y)

    x_train, x_val, y_train, y_val = train_test_split(
        x, y, test_size=0.2, random_state=seed
    )

    param = {"objective": "mape", "verbose": -1}
    train_data = lgb.Dataset(
        x_train, label=y_train, feature_name=PgFeatureMapper.get_names(), params=param
    )
    val_data = lgb.Dataset(x_val, label=y_val, reference=train_data, params=param)
    bst = lgb.Booster(param, train_data)
    bst.add_valid(val_data, "val_data")

    for _ in range(num_trees):
        bst.update()
    return bst


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train a query-level T3 variant on zero-shot parsed plans "
            "with one benchmark held out as test set."
        )
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(DEFAULT_DATA_DIR),
        help=f"Root directory containing zero-shot JSON files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output model path (default: model_zero_holdout_<holdout>_ql.txt; if exists, saves to _v1, _v2, ...)",
    )
    parser.add_argument(
        "--holdout",
        type=str,
        default=HOLDOUT_BENCHMARK,
        help=f"Benchmark folder name to hold out as test set (default: {HOLDOUT_BENCHMARK})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for train/val split (default: {SEED})",
    )
    parser.add_argument(
        "--use-estimated-card",
        action="store_true",
        help="Use estimated cardinalities (est_card) instead of actual; same feature names.",
    )
    args = parser.parse_args()

    if args.out is None:
        args.out = Path(f"model_zero_holdout_{args.holdout}_ql.txt")

    use_actual_card = not args.use_estimated_card

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(data_dir)
    if not all_json_paths:
        print(f"No .json files under {data_dir}")
        sys.exit(1)

    train_paths, test_paths = split_train_test_by_holdout(
        all_json_paths, holdout_name=args.holdout
    )

    if not train_paths:
        print(f"Error: no train files (all paths contain '{args.holdout}').")
        sys.exit(1)

    print(f"JSON files: {len(all_json_paths)} total")
    print(f"Train (all except {args.holdout}): {len(train_paths)} files")
    print(f"Test ({args.holdout}): {len(test_paths)} files")

    train_queries = load_benchmarked_queries_from_zeroshot(
        train_paths, use_actual_card=use_actual_card
    )
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train benchmarks (plans)")

    bst = train_query_level_lightgbm(train_queries, seed=args.seed)
    base_out = args.out if args.out.is_absolute() else _repo / args.out
    out_path = next_available_model_path(_repo, base_out)
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    feature_mapper = PgFeatureMapper()

    if test_paths:
        test_queries = load_benchmarked_queries_from_zeroshot(
            test_paths, use_actual_card=use_actual_card
        )
        if test_queries:
            errors = []
            for b in test_queries:
                pred = estimate_runtime_query_level(bst, b, feature_mapper)
                actual = b.get_total_runtime()
                err = q_error(actual, pred)
                errors.append(err)
                print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")
            summary = (
                f"Test set ({args.holdout}, {len(test_queries)} queries) [query-level]: "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} "
                f"p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} "
                f"max={max(errors):.4f} model={out_path.name}"
            )
            print(summary)
            holdout_path = _repo / "holdout.txt"
            with open(holdout_path, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"Test results appended to {holdout_path}")
        else:
            print(f"No test queries could be loaded from {len(test_paths)} test files.")
    else:
        print(f"No test files (no path contains '{args.holdout}').")


if __name__ == "__main__":
    main()
