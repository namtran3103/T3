"""
Train T3 per-tuple model on zero-shot parsed plan JSONs.

Uses 80% of JSONs as training and 20% as validation (seed 42). Each JSON file can contain
multiple parsed plans (parsed_plans array); each plan is converted to T3, split into pipelines
(hash, materialize, sort, aggregate as breakers), and used for feature-vector generation.

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot --data /path/to/zero-shot-data/runs/parsed_plans
  python -m src.zeroshot.training_zeroshot --data /path/to/parsed_plans --out model_zero.txt
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
TRAIN_FRACTION = 0.8
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
DEFAULT_MODEL_PATH = "model_zero.txt"


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
    """Train per-tuple tree model on pipeline feature vectors (same as training_job_extended)."""
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train T3 on zero-shot parsed plans (80/20 split, seed 42)."
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
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for 80/20 split (default: {SEED})",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=TRAIN_FRACTION,
        help=f"Fraction of data for training (default: {TRAIN_FRACTION})",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip printing validation set metrics",
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

    # Split by files: 80% of files train, 20% validation (seed 42)
    rng = np.random.default_rng(args.seed)
    indices = rng.permutation(len(all_json_paths))
    shuffled = [all_json_paths[i] for i in indices]
    n_train = int(round(len(shuffled) * args.train_fraction))
    n_train = max(1, min(n_train, len(shuffled) - 1))
    train_paths = shuffled[:n_train]
    val_paths = shuffled[n_train:]

    print(f"JSON files: {len(all_json_paths)} total")
    print(f"Train: {len(train_paths)} files ({100 * len(train_paths) / len(all_json_paths):.0f}%)")
    print(f"Val:   {len(val_paths)} files")

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

    if not args.no_eval and val_paths:
        val_queries = load_benchmarked_queries_from_zeroshot(val_paths)
        if val_queries:
            errors = []
            for b in val_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                err = q_error(actual, pred)
                errors.append(err)
                print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")
            print(
                f"Validation set ({len(val_queries)} queries): "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} max={max(errors):.4f}"
            )


if __name__ == "__main__":
    main()
