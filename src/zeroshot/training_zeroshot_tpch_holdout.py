"""
Train T3 on zero-shot parsed plans with TPC-H held out as test set.

Train on all JSONs except those under the TPC-H directory; use TPC-H as the test set
(leave-one-benchmark-out). Same conversion and training as training_zeroshot; only the
split changes (by path: paths containing the holdout name, e.g. "tpc_h", are test).

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_tpch_holdout
  python -m src.zeroshot.training_zeroshot_tpch_holdout --data /path/to/parsed_plans --out model_zero_tpch_holdout.txt
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
from src.model import FeatureMapper, PerTupleTreeModel
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


def load_benchmarked_queries_from_zeroshot(
    json_paths: list[Path],
    use_actual_card: bool = True,
) -> list[BenchmarkedQuery]:
    """Build BenchmarkedQuery list from zero-shot JSON paths. One query per parsed plan in each file."""
    db = get_minimal_database()
    queries: list[BenchmarkedQuery] = []
    for jf in json_paths:
        try:
            data = load_zeroshot_json(jf)
            plans = data.get("parsed_plans", [])
            for idx, zs_plan in enumerate(plans):
                try:
                    converted = zeroshot_plan_to_t3(zs_plan, use_actual_card=use_actual_card)
                    runtime_sec = converted.get("plan_runtime_seconds")
                    if runtime_sec is None or runtime_sec <= 0:
                        continue
                    plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
                    plan.build_pipelines(converted["analyzePlanPipelines"])
                    name = f"{jf.stem}_{idx}" if len(plans) > 1 else jf.stem
                    b = BenchmarkedQuery(plan, [runtime_sec], name, "", QueryCategory.fixed)
                    queries.append(b)
                except Exception:
                    continue
        except Exception:
            continue
    return queries


def train_per_tuple_model(
    queries: list[BenchmarkedQuery],
    seed: int = SEED,
    verbose: bool = True,
) -> tuple[PerTupleTreeModel, lgb.Booster]:
    """Train per-tuple tree model on pipeline feature vectors."""
    feature_mapper = FeatureMapper()
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
    param = {"objective": "mape", "verbose": 2 if verbose else -1}
    train_data = lgb.Dataset(
        x_train, label=y_train, feature_name=FeatureMapper.get_names(), params=param
    )
    val_data = lgb.Dataset(x_val, label=y_val, reference=train_data, params=param)
    bst = lgb.Booster(param, train_data)
    bst.add_valid(val_data, "val_data")
    if verbose:
        print("Initial:", bst.eval_train(), bst.eval_valid())
    for i in range(200):
        bst.update()
        if verbose and (i + 1) % 50 == 0:
            print(i + 1, bst.eval_train(), bst.eval_valid())
    if verbose:
        print("Final:", bst.eval_train(), bst.eval_valid())
    return PerTupleTreeModel(bst), bst


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
        default=Path(DEFAULT_MODEL_PATH),
        help=f"Output model path (default: {DEFAULT_MODEL_PATH})",
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
        help=f"Random seed for internal train/val split during training (default: {SEED})",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip printing test set metrics",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Less training output",
    )
    args = parser.parse_args()

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

    train_queries = load_benchmarked_queries_from_zeroshot(train_paths)
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train benchmarks (plans)")

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet
    )
    out_path = args.out if args.out.is_absolute() else _repo / args.out
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if not args.no_eval and test_paths:
        test_queries = load_benchmarked_queries_from_zeroshot(test_paths)
        if test_queries:
            errors = []
            lines = [f"holdout={args.holdout}", ""]
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                err = q_error(actual, pred)
                errors.append(err)
                line = f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}"
                print(line)
                lines.append(line)
            summary = (
                f"Test set ({args.holdout}, {len(test_queries)} queries): "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} max={max(errors):.4f}"
            )
            print(summary)
            lines.append("")
            lines.append(summary)
            holdout_path = _repo / "holdout.txt"
            with open(holdout_path, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            print(f"Test results appended to {holdout_path}")
        else:
            print(f"No test queries could be loaded from {len(test_paths)} test files.")
    elif not args.no_eval and not test_paths:
        print(f"No test files (no path contains '{args.holdout}').")


if __name__ == "__main__":
    main()
