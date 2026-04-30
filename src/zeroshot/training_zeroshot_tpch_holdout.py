"""
Train T3 on zero-shot parsed plans with one benchmark held out as test set.

Train on all JSONs except those under the holdout directory; use the holdout as the test set
(leave-one-benchmark-out). Same conversion and training as training_zeroshot; only the
split changes (by path: paths containing the holdout name are test).

If the output file already exists, saves to _v1, _v2, ... (next free number). Appends
test summary to holdout.txt (append, no overwrite).

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_tpch_holdout
  python -m src.zeroshot.training_zeroshot_tpch_holdout --data /path/to/parsed_plans --out model_zero_tpch_holdout.txt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split

from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.pg_features import PgFeatureMapper
from src.optimizer import BenchmarkedQuery, QueryCategory
from src.query_plan import QueryPlan
from src.zeroshot.zeroshot_to_t3 import (
    get_minimal_database,
    load_zeroshot_json,
    zeroshot_plan_to_t3,
    collect_all_zeroshot_jsons,
)

SEED = 42
HOLDOUT_BENCHMARK = "tpc_h"
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
DEFAULT_MODEL_PATH = "model_zero_tpch_holdout.txt"


def next_available_model_path(repo: Path, base_path: Path) -> Path:
    """If base_path exists, return base_path.stem + _vN + suffix for next free N; else return base_path."""
    resolved = base_path if base_path.is_absolute() else repo / base_path
    if not resolved.exists():
        return resolved
    stem = resolved.stem
    suffix = resolved.suffix
    n = 1
    while True:
        candidate = resolved.parent / f"{stem}_v{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def load_benchmarked_queries_from_zeroshot(
    json_paths: list[Path],
    use_actual_card: bool = True,
) -> list[BenchmarkedQuery]:
    """Build BenchmarkedQuery list from zero-shot JSON paths. One query per parsed plan in each file."""
    db = get_minimal_database()
    queries: list[BenchmarkedQuery] = []
    for jf in json_paths:
        skip_no_runtime = 0
        skip_exception = 0
        added_this_file = 0
        try:
            data = load_zeroshot_json(jf)
            plans = data.get("parsed_plans", [])
            for idx, zs_plan in enumerate(plans):
                try:
                    converted = zeroshot_plan_to_t3(zs_plan, use_actual_card=use_actual_card)
                    runtime_sec = converted.get("plan_runtime_seconds")
                    if runtime_sec is None or runtime_sec <= 0:
                        skip_no_runtime += 1
                        logger.warning(
                            "Skipping plan %s_%s: no or invalid plan_runtime_seconds (got %s)",
                            jf.stem,
                            idx,
                            runtime_sec,
                        )
                        continue
                    plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
                    plan.build_pipelines(converted["analyzePlanPipelines"])
                    name = f"{jf.stem}_{idx}" if len(plans) > 1 else jf.stem
                    b = BenchmarkedQuery(plan, [runtime_sec], name, "", QueryCategory.fixed, plan_dict=converted)
                    queries.append(b)
                    added_this_file += 1
                except Exception as e:
                    skip_exception += 1
                    logger.warning(
                        "Skipping plan %s_%s: conversion or pipeline build failed: %s",
                        jf.stem,
                        idx,
                        e,
                        exc_info=True,
                    )
                    continue
            if skip_no_runtime or skip_exception:
                logger.info(
                    "Loaded %s from %s: %s ok, %s skipped (no runtime), %s skipped (exception)",
                    jf.name,
                    added_this_file,
                    skip_no_runtime,
                    skip_exception,
                )
        except Exception as e:
            logger.warning("Failed to load file %s: %s", jf, e, exc_info=True)
            continue
    return queries


def train_zeroshot_pipeline_lightgbm(
    queries: list[BenchmarkedQuery],
    seed: int = SEED,
    num_trees: int = 200,
) -> tuple[PerTupleTreeModel, lgb.Booster]:
    """
    Train LightGBM on PG pipeline feature rows, same train/val protocol as
    optimize_per_tuple_tree_model (random 80/20 split over stacked pipeline rows).

    Labels are taken from get_per_tuple_pipeline_runtime_data; with PgFeatureMapper,
    get_pipeline_scan_sizes is all ones, so each label is the observed pipeline
    duration (not a true per-tuple time). num_trees: boosting rounds.
    """
    feature_mapper = PgFeatureMapper()
    x_vectors = []
    y_values = []
    for query in queries:
        for x, y in query.get_per_tuple_pipeline_runtime_data(feature_mapper):
            if np.any(x != 0):
                x_vectors.append(x)
                y_values.append(y)
    if not x_vectors:
        raise ValueError(
            "No pipeline rows with non-zero features. Check zero-shot plans and conversions."
        )
    x = np.vstack(x_vectors)
    y = np.array(y_values)
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

    for i in range(num_trees):
        bst.update()
    return PerTupleTreeModel(bst, feature_mapper=feature_mapper), bst


def split_train_test_by_holdout(
    all_paths: list[Path],
    holdout_name: str = HOLDOUT_BENCHMARK,
) -> tuple[list[Path], list[Path]]:
    """Split paths: test = paths containing holdout_name (e.g. tpc_h), train = rest."""
    test_paths = [p for p in all_paths if holdout_name in p.parts]
    train_paths = [p for p in all_paths if p not in set(test_paths)]
    return train_paths, test_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train T3 on zero-shot parsed plans with TPC-H held out as test set."
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
        help="Output model path (default: model_zero_holdout_<holdout>.txt; if exists, saves to _v1, _v2, ...)",
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
        help=(
            f"Random seed for train/val split over pipeline rows (Umbra-core style; default: {SEED})"
        ),
    )
    parser.add_argument(
        "--use-estimated-card",
        action="store_true",
        help="Use estimated cardinalities (est_card) instead of actual; same feature names.",
    )
    args = parser.parse_args()

    if args.out is None:
        args.out = Path(f"model_zero_holdout_{args.holdout}.txt")

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

    model, bst = train_zeroshot_pipeline_lightgbm(train_queries, seed=args.seed)
    base_out = args.out if args.out.is_absolute() else _repo / args.out
    out_path = next_available_model_path(_repo, base_out)
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if test_paths:
        test_queries = load_benchmarked_queries_from_zeroshot(test_paths, use_actual_card=use_actual_card)
        if test_queries:
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                err = q_error(actual, pred)
                errors.append(err)
                print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")
            summary = (
                f"Test set ({args.holdout}, {len(test_queries)} queries): "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p90={np.percentile(errors, 90):.4f} model={out_path.name}"
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
