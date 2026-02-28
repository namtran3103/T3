"""
Train T3 (Johannes pipeline) on a single holdout only: train and test on the same data (overfitting).

Uses only JSON files from the specified holdout directory (e.g. imdb_full). Both training
and evaluation use this same data. Default holdout is imdb_full.
Appends diagnostics to diagnostics_training_jh.txt and test summary to holdout_jh.txt
(same format as training_jh_holdout, with overfit=true).

Usage (from T3 repo root, PYTHONPATH=. or default):
  python -m src.t3_jh.training_jh_overfit_holdout
  python -m src.t3_jh.training_jh_overfit_holdout --holdout tpc_h
  python -m src.t3_jh.training_jh_overfit_holdout --data /path/to/parsed_plans --holdout imdb_full
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.metrics import q_error

from .jh_dataloader import load_parsed_plans_from_json, collect_all_jsons
from .training_jh_holdout import (
    train_per_tuple_model,
    next_available_model_path,
    append_diagnostics,
    SEED,
)

DEFAULT_HOLDOUT = "imdb_full"
DEFAULT_MODEL_PREFIX = "model_jh_overfit"
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
DIAGNOSTICS_FILE = "diagnostics_training_jh.txt"
HOLDOUT_FILE = "holdout_jh.txt"


def get_holdout_paths(all_paths: list, holdout_name: str) -> list:
    """Return only paths that contain the holdout name (e.g. imdb_full in path parts)."""
    return [p for p in all_paths if holdout_name in p.parts]


def main():
    parser = argparse.ArgumentParser(
        description="Train T3 (Johannes) on a single holdout only (overfit: train and test on same data)."
    )
    parser.add_argument("--data", type=Path, default=Path(DEFAULT_DATA_DIR))
    parser.add_argument("--holdout", type=str, default=DEFAULT_HOLDOUT)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output model path (default: {DEFAULT_MODEL_PREFIX}_<holdout>.txt, or _v1, _v2, ... if exists)",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--no-eval", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Print detailed load diagnostics")
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_paths = collect_all_jsons(data_dir)
    if not all_paths:
        print(f"No .json under {data_dir}")
        sys.exit(1)

    holdout_paths = get_holdout_paths(all_paths, args.holdout)
    if not holdout_paths:
        available = sorted(set(p.parts[0] for p in all_paths if len(p.parts) > 1))
        print(f"Error: no files found for holdout '{args.holdout}'.")
        print(f"Available holdouts: {available}")
        sys.exit(1)

    train_paths = test_paths = holdout_paths

    print(f"Overfit holdout ({args.holdout}): {len(holdout_paths)} files (train=test=same)")

    train_queries, train_diag = load_parsed_plans_from_json(
        train_paths, verbose=args.verbose or True
    )

    if not train_queries:
        print("No train queries loaded. Fix errors above or adjust data/holdout.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} benchmarks for training")

    append_diagnostics(args.holdout, train_diag, len(train_queries), _repo)

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet
    )

    default_model = Path(f"{DEFAULT_MODEL_PREFIX}_{args.holdout}.txt")
    base_out = args.out if args.out is not None else default_model
    out_path = next_available_model_path(_repo, base_out)
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if not args.no_eval and test_paths:
        test_queries, _ = load_parsed_plans_from_json(test_paths)
        if test_queries:
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                if pred <= 0:
                    pred = 1e-9
                err = q_error(actual, pred)
                errors.append(err)
            errors = np.array(errors)
            summary = (
                f"holdout={args.holdout} overfit=true n={len(test_queries)} "
                f"min={np.min(errors):.4f} max={np.max(errors):.4f} avg={np.mean(errors):.4f} "
                f"p50={np.percentile(errors, 50):.4f} p75={np.percentile(errors, 75):.4f} p90={np.percentile(errors, 90):.4f}"
            )
            print(summary)
            with open(_repo / HOLDOUT_FILE, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"Results appended to {_repo / HOLDOUT_FILE}")
        else:
            print("No test queries loaded.")
    elif not args.no_eval and not test_paths:
        print(f"No test files for holdout '{args.holdout}'.")


if __name__ == "__main__":
    main()
