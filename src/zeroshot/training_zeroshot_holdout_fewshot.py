"""
Few-shot finetune a zero-shot holdout model on queries from the holdout benchmark.

Loads model_zero_holdout_<holdout>.txt, selects up to N queries (default 50) evenly
distributed over the holdout's JSON files (seed 42), continues LightGBM training for a
small number of rounds, and saves model_zero_holdout_<holdout>_fewshot.txt.
Test-set summary is appended to holdout_fewshot.txt.

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_holdout_fewshot
  python -m src.zeroshot.training_zeroshot_holdout_fewshot --holdout tpc_h --num-queries 50
"""

from __future__ import annotations

import argparse
import random
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
DEFAULT_NUM_QUERIES = 50
DEFAULT_NUM_BOOST_ROUND = 30


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


def split_train_test_by_holdout(
    all_paths: list[Path],
    holdout_name: str,
) -> tuple[list[Path], list[Path]]:
    """Split paths: test = paths containing holdout_name, train = rest."""
    test_paths = [p for p in all_paths if holdout_name in p.parts]
    train_paths = [p for p in all_paths if p not in set(test_paths)]
    return train_paths, test_paths


def sample_queries_evenly_by_file(
    test_paths: list[Path],
    max_queries: int,
    seed: int = SEED,
) -> list[BenchmarkedQuery]:
    """
    Load queries from test_paths, then select up to max_queries evenly distributed
    over the JSON files (same seed for reproducibility).
    """
    # Load per-file so we can distribute evenly
    by_file: list[tuple[Path, list[BenchmarkedQuery]]] = []
    for jf in sorted(test_paths):
        queries = load_benchmarked_queries_from_zeroshot([jf])
        if queries:
            by_file.append((jf, queries))
    if not by_file:
        return []
    total = sum(len(q) for _, q in by_file)
    n = min(max_queries, total)
    num_files = len(by_file)
    rng = random.Random(seed)
    # Target count per file: as equal as possible, sum = n
    base = n // num_files
    remainder = n % num_files
    targets = [base + (1 if i < remainder else 0) for i in range(num_files)]
    selected: list[BenchmarkedQuery] = []
    for i, (_, queries) in enumerate(by_file):
        k = min(targets[i], len(queries))
        selected.extend(rng.sample(queries, k))
    return selected


def finetune_per_tuple_model(
    initial_bst: lgb.Booster,
    queries: list[BenchmarkedQuery],
    seed: int = SEED,
    num_boost_round: int = DEFAULT_NUM_BOOST_ROUND,
    verbose: bool = True,
) -> tuple[PerTupleTreeModel, lgb.Booster]:
    """Continue training (finetune) the given booster on the given queries."""
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
    bst = lgb.train(
        param,
        train_data,
        num_boost_round=num_boost_round,
        init_model=initial_bst,
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
    )
    if verbose:
        print("Finetune rounds:", num_boost_round)
    return PerTupleTreeModel(bst), bst


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Few-shot finetune a zero-shot holdout model on holdout queries."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(DEFAULT_DATA_DIR),
        help=f"Root directory containing zero-shot JSON files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--holdout",
        type=str,
        default=HOLDOUT_BENCHMARK,
        help=f"Benchmark folder name (holdout) to finetune on (default: {HOLDOUT_BENCHMARK})",
    )
    parser.add_argument(
        "--num-queries",
        type=int,
        default=DEFAULT_NUM_QUERIES,
        help=f"Max number of holdout queries to use for finetuning (default: {DEFAULT_NUM_QUERIES})",
    )
    parser.add_argument(
        "--num-boost-round",
        type=int,
        default=DEFAULT_NUM_BOOST_ROUND,
        help=f"Number of additional boosting rounds (default: {DEFAULT_NUM_BOOST_ROUND})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for even distribution over files and train/val split (default: {SEED})",
    )
    parser.add_argument(
        "--model-in",
        type=Path,
        default=None,
        help="Input model path (default: model_zero_holdout_<holdout>.txt)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output model path (default: ..._fewshot.txt or ..._fewshot_<num_queries>.txt if num-queries != 50)",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip printing test set metrics and appending to holdout_fewshot.txt",
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

    _, test_paths = split_train_test_by_holdout(all_json_paths, args.holdout)
    if not test_paths:
        print(f"No test files (no path contains '{args.holdout}').")
        sys.exit(1)

    fewshot_queries = sample_queries_evenly_by_file(
        test_paths, args.num_queries, seed=args.seed
    )
    if not fewshot_queries:
        print("Error: no few-shot queries could be loaded from holdout files.")
        sys.exit(1)
    print(f"Using {len(fewshot_queries)} queries for finetuning (max {args.num_queries}, seed {args.seed})")

    model_in = args.model_in
    if model_in is None:
        model_in = _repo / f"model_zero_holdout_{args.holdout}.txt"
    else:
        model_in = model_in if model_in.is_absolute() else _repo / model_in
    if not model_in.exists():
        print(f"Error: initial model not found: {model_in}")
        sys.exit(1)

    initial_bst = lgb.Booster(model_file=str(model_in))
    model, bst = finetune_per_tuple_model(
        initial_bst,
        fewshot_queries,
        seed=args.seed,
        num_boost_round=args.num_boost_round,
        verbose=not args.quiet,
    )

    out_path = args.out
    if out_path is None:
        if args.num_queries == DEFAULT_NUM_QUERIES:
            out_path = _repo / f"model_zero_holdout_{args.holdout}_fewshot.txt"
        else:
            out_path = _repo / f"model_zero_holdout_{args.holdout}_fewshot_{args.num_queries}.txt"
    else:
        out_path = out_path if out_path.is_absolute() else _repo / out_path
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if not args.no_eval and test_paths:
        test_queries = load_benchmarked_queries_from_zeroshot(test_paths)
        if test_queries:
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                err = q_error(actual, pred)
                errors.append(err)
                if not args.quiet:
                    print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")
            summary = (
                f"Test set ({args.holdout}, {len(test_queries)} queries): "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} max={max(errors):.4f}"
            )
            print(summary)
            if args.num_queries == DEFAULT_NUM_QUERIES:
                holdout_path = _repo / "holdout_fewshot.txt"
            else:
                holdout_path = _repo / f"holdout_fewshot_{args.num_queries}.txt"
            with open(holdout_path, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"Test results appended to {holdout_path}")


if __name__ == "__main__":
    main()
