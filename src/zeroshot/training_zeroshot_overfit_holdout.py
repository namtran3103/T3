"""
Train T3 on a single holdout only: train and test on the same data (overfitting).

Uses only JSON files from the specified holdout directory (e.g. imdb_full). Both training
and evaluation use this same data. Default holdout is imdb_full.

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_overfit_holdout
  python -m src.zeroshot.training_zeroshot_overfit_holdout --holdout tpc_h
  python -m src.zeroshot.training_zeroshot_overfit_holdout --num-trees 500
  python -m src.zeroshot.training_zeroshot_overfit_holdout --data /path/to/parsed_plans --holdout imdb_full
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
from src.metrics import q_error
from src.zeroshot.training_zeroshot_tpch_holdout import (
    load_benchmarked_queries_from_zeroshot,
    load_benchmarked_queries_from_zeroshot_with_diagnostics,
    train_zeroshot_pipeline_lightgbm,
    next_available_model_path,
    SEED,
)

DEFAULT_NUM_TREES = 200
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons

DIAGNOSTICS_FILE = "diagnostics_training.txt"
DEFAULT_HOLDOUT = "imdb_full"
DEFAULT_MODEL_PREFIX = "model_overfit"
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"


def get_holdout_paths(all_paths: list[Path], holdout_name: str) -> list[Path]:
    """Return only paths that contain the holdout name (e.g. imdb_full in path parts)."""
    return [p for p in all_paths if holdout_name in p.parts]


def _append_training_diagnostics(
    holdout: str,
    diagnostics: list[dict],
    total_queries: int,
    mode: str = "overfit",
) -> None:
    """Append training diagnostics to diagnostics_training.txt with timestamp and holdout."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = _repo / DIAGNOSTICS_FILE
    lines = [
        "",
        "---",
        f"timestamp={ts}",
        f"holdout={holdout}",
        f"mode={mode}",
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train T3 on a single holdout only (overfit: train and test on same data)."
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
        default=DEFAULT_HOLDOUT,
        help=f"Holdout benchmark to overfit (default: {DEFAULT_HOLDOUT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output model path (default: {DEFAULT_MODEL_PREFIX}_<holdout>.txt, or _v1, _v2, ... if exists)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for internal train/val split during training (default: {SEED})",
    )
    parser.add_argument(
        "--num-trees",
        type=int,
        default=DEFAULT_NUM_TREES,
        metavar="N",
        help=f"LightGBM boosting rounds (per-tuple model) (default: {DEFAULT_NUM_TREES})",
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
    if args.num_trees < 1:
        print("Error: --num-trees must be >= 1")
        sys.exit(1)

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(data_dir)
    if not all_json_paths:
        print(f"No .json files under {data_dir}")
        sys.exit(1)

    holdout_paths = get_holdout_paths(all_json_paths, args.holdout)
    if not holdout_paths:
        print(f"Error: no files found for holdout '{args.holdout}'.")
        print(f"Available holdouts (from path parts): {sorted(set(p.parts[0] for p in all_json_paths if len(p.parts) > 1))}")
        sys.exit(1)

    # Train and test on the SAME holdout data (overfitting)
    train_paths = test_paths = holdout_paths

    print(f"JSON files: {len(all_json_paths)} total")
    print(
        f"Overfit holdout ({args.holdout}): {len(holdout_paths)} files "
        f"(train=test=same), num_trees={args.num_trees}"
    )

    train_queries, train_diagnostics = load_benchmarked_queries_from_zeroshot_with_diagnostics(
        train_paths
    )
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} benchmarks (plans) for training")

    _append_training_diagnostics(
        holdout=args.holdout,
        diagnostics=train_diagnostics,
        total_queries=len(train_queries),
        mode="overfit",
    )

    model, bst = train_zeroshot_pipeline_lightgbm(
        train_queries,
        seed=args.seed,
        verbose=not args.quiet,
        num_trees=args.num_trees,
    )

    default_model = Path(f"{DEFAULT_MODEL_PREFIX}_{args.holdout}.txt")
    base_out = args.out if args.out is not None else default_model
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
                if not args.quiet:
                    print(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")
            summary = (
                f"Overfit test ({args.holdout}, {len(test_queries)} queries, train=test): "
                f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} "
                f"p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} max={max(errors):.4f}"
            )
            print(summary)
            holdout_path = _repo / "holdout.txt"
            with open(holdout_path, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"Test results appended to {holdout_path}")
        else:
            print(f"No test queries could be loaded from {len(test_paths)} test files.")


if __name__ == "__main__":
    main()
