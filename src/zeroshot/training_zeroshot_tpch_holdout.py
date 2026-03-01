"""
Train T3 on zero-shot parsed plans with one benchmark held out as test set.

Train on all JSONs except those under the holdout directory; use the holdout as the test set
(leave-one-benchmark-out). Same conversion and training as training_zeroshot; only the
split changes (by path: paths containing the holdout name are test).

If the output file already exists, saves to _v1, _v2, ... (next free number). Appends
training diagnostics to diagnostics_training.txt and test summary to holdout.txt (append,
no overwrite).

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_tpch_holdout
  python -m src.zeroshot.training_zeroshot_tpch_holdout --data /path/to/parsed_plans --out model_zero_tpch_holdout.txt
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
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
DIAGNOSTICS_FILE = "diagnostics_training.txt"


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


def _append_training_diagnostics(
    holdout: str,
    diagnostics: list[dict],
    total_queries: int,
) -> None:
    """Append training diagnostics to diagnostics_training.txt with timestamp and holdout."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = _repo / DIAGNOSTICS_FILE
    lines = [
        "",
        "---",
        f"timestamp={ts}",
        f"holdout={holdout}",
        f"train_files={len(diagnostics)}",
        f"total_queries_used={total_queries}",
        "",
    ]
    total_plans = 0
    total_added = 0
    total_skip_no_runtime = 0
    total_skip_exception = 0
    files_failed = 0
    for d in diagnostics:
        total_plans += d["plans_total"]
        total_added += d["added"]
        total_skip_no_runtime += d["skip_no_runtime"]
        total_skip_exception += d["skip_exception"]
        if d.get("file_error"):
            files_failed += 1
        status = "ok" if d["added"] == d["plans_total"] and not d.get("file_error") else "skipped_some"
        line = (
            f"  {d['path']}: plans={d['plans_total']} added={d['added']} "
            f"skip_no_runtime={d['skip_no_runtime']} skip_exception={d['skip_exception']}"
        )
        if d.get("file_error"):
            line += f" file_error={d['file_error']!r}"
        line += f" [{status}]"
        lines.append(line)
    lines.extend([
        "",
        f"total_plans={total_plans} total_added={total_added} "
        f"total_skip_no_runtime={total_skip_no_runtime} total_skip_exception={total_skip_exception} "
        f"files_failed={files_failed}",
        "",
    ])
    with open(out_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Training diagnostics appended to {out_path}")


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


def load_benchmarked_queries_from_zeroshot_with_diagnostics(
    json_paths: list[Path],
    use_actual_card: bool = True,
) -> tuple[list[BenchmarkedQuery], list[dict]]:
    """Like load_benchmarked_queries_from_zeroshot but also return per-file diagnostics.
    Returns (queries, diagnostics) where each diagnostic dict has: path, plans_total, added,
    skip_no_runtime, skip_exception, file_error (str or None if file loaded)."""
    db = get_minimal_database()
    queries: list[BenchmarkedQuery] = []
    diagnostics: list[dict] = []
    for jf in json_paths:
        skip_no_runtime = 0
        skip_exception = 0
        added_this_file = 0
        plans_total = 0
        file_error: str | None = None
        try:
            data = load_zeroshot_json(jf)
            plans = data.get("parsed_plans", [])
            plans_total = len(plans)
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
            file_error = f"{type(e).__name__}: {e}"
            logger.warning("Failed to load file %s: %s", jf, e, exc_info=True)
        diagnostics.append({
            "path": str(jf),
            "plans_total": plans_total,
            "added": added_this_file,
            "skip_no_runtime": skip_no_runtime,
            "skip_exception": skip_exception,
            "file_error": file_error,
        })
    return queries, diagnostics


def train_per_tuple_model(
    queries: list[BenchmarkedQuery],
    seed: int = SEED,
    verbose: bool = True,
    num_trees: int = 200,
) -> tuple[PerTupleTreeModel, lgb.Booster]:
    """Train per-tuple tree model on pipeline feature vectors (PG features for zeroshot). num_trees: number of boosting rounds."""
    feature_mapper = PgFeatureMapper()
    # Split by query so validation q-error is per-query (total runtime vs total predicted), same as test set.
    train_idx, val_idx = train_test_split(
        np.arange(len(queries)), test_size=0.2, random_state=seed
    )
    train_queries = [queries[i] for i in train_idx]
    val_queries = [queries[i] for i in val_idx]

    x_vectors = []
    y_values = []
    for query in train_queries:
        for x, y in query.get_per_tuple_pipeline_runtime_data(feature_mapper):
            if np.any(x != 0):
                x_vectors.append(x)
                y_values.append(y)
    if not x_vectors:
        raise ValueError(
            "No pipeline rows with non-zero features. Check zero-shot plans and conversions."
        )
    x_train = np.vstack(x_vectors)
    y_train = np.array(y_values)
    y_train = np.maximum(y_train, 1e-15)
    y_train = -np.log(y_train)

    x_val_vec = []
    y_val_vec = []
    for query in val_queries:
        for x, y in query.get_per_tuple_pipeline_runtime_data(feature_mapper):
            if np.any(x != 0):
                x_val_vec.append(x)
                y_val_vec.append(y)
    x_val = np.vstack(x_val_vec) if x_val_vec else np.zeros((0, x_train.shape[1]))
    y_val = np.array(y_val_vec) if y_val_vec else np.array([])
    if len(y_val) > 0:
        y_val = np.maximum(y_val, 1e-15)
        y_val = -np.log(y_val)

    param = {"objective": "mape", "verbose": 2 if verbose else -1}
    train_data = lgb.Dataset(
        x_train, label=y_train, feature_name=PgFeatureMapper.get_names(), params=param
    )
    val_data = lgb.Dataset(x_val, label=y_val, reference=train_data, params=param)
    bst = lgb.Booster(param, train_data)
    bst.add_valid(val_data, "val_data")

    def _val_avg_q_error():
        if not val_queries:
            return float("nan")
        model = PerTupleTreeModel(bst, feature_mapper=feature_mapper)
        errors = [
            q_error(q.get_total_runtime(), model.estimate_runtime(q))
            for q in val_queries
        ]
        return float(np.mean(errors))

    if verbose:
        print("Initial:", bst.eval_train(), bst.eval_valid(), "valid_avg_q_error={:.4f}".format(_val_avg_q_error()))
    for i in range(num_trees):
        bst.update()
        if verbose and (i + 1) % 50 == 0:
            print(i + 1, bst.eval_train(), bst.eval_valid(), "valid_avg_q_error={:.4f}".format(_val_avg_q_error()))
    if verbose:
        print("Final:", bst.eval_train(), bst.eval_valid(), "valid_avg_q_error={:.4f}".format(_val_avg_q_error()))
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
        default=Path(DEFAULT_MODEL_PATH),
        help=f"Output model path (default: {DEFAULT_MODEL_PATH}; if exists, saves to _v1, _v2, ...)",
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

    train_queries, train_diagnostics = load_benchmarked_queries_from_zeroshot_with_diagnostics(
        train_paths
    )
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train benchmarks (plans)")

    _append_training_diagnostics(
        holdout=args.holdout,
        diagnostics=train_diagnostics,
        total_queries=len(train_queries),
    )

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet
    )
    base_out = args.out if args.out.is_absolute() else _repo / args.out
    out_path = next_available_model_path(_repo, base_out)
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
                print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")
            summary = (
                f"Test set ({args.holdout}, {len(test_queries)} queries): "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} max={max(errors):.4f}"
            )
            print(summary)
            holdout_path = _repo / "holdout.txt"
            with open(holdout_path, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"Test results appended to {holdout_path}")
        else:
            print(f"No test queries could be loaded from {len(test_paths)} test files.")
    elif not args.no_eval and not test_paths:
        print(f"No test files (no path contains '{args.holdout}').")


if __name__ == "__main__":
    main()
