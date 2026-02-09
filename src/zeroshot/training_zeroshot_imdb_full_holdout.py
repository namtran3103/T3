"""
Train T3 on zero-shot parsed plans with imdb_full held out as test set.

Same as training_zeroshot_tpch_holdout but with imdb_full as the holdout and
default output model_zero_holdout_imdb_full.txt. If that file already exists,
saves to model_zero_holdout_imdb_full_v1.txt, then _v2, etc. (next free number).

Usage (from T3 project root):
  python -m src.zeroshot.training_zeroshot_imdb_full_holdout
  python -m src.zeroshot.training_zeroshot_imdb_full_holdout --data /path/to/parsed_plans
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
    train_per_tuple_model,
    split_train_test_by_holdout,
    SEED,
)
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons

DIAGNOSTICS_FILE = "diagnostics_training.txt"

HOLDOUT_IMDB_FULL = "imdb_full"
DEFAULT_MODEL_PATH = "model_zero_holdout_imdb_full.txt"
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train T3 on zero-shot parsed plans with imdb_full held out as test set."
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
        help=f"Output model path (default: {DEFAULT_MODEL_PATH}, or _v1, _v2, ... if file exists)",
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
        all_json_paths, holdout_name=HOLDOUT_IMDB_FULL
    )

    if not train_paths:
        print(f"Error: no train files (all paths contain '{HOLDOUT_IMDB_FULL}').")
        sys.exit(1)

    print(f"JSON files: {len(all_json_paths)} total")
    print(f"Train (all except {HOLDOUT_IMDB_FULL}): {len(train_paths)} files")
    print(f"Test ({HOLDOUT_IMDB_FULL}): {len(test_paths)} files")

    train_queries, train_diagnostics = load_benchmarked_queries_from_zeroshot_with_diagnostics(
        train_paths
    )
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train benchmarks (plans)")

    # Append training diagnostics to diagnostics_training.txt (timestamp + holdout + per-file stats)
    _append_training_diagnostics(
        holdout=HOLDOUT_IMDB_FULL,
        diagnostics=train_diagnostics,
        total_queries=len(train_queries),
    )

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet
    )

    base_out = args.out if args.out is not None else Path(DEFAULT_MODEL_PATH)
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
                f"Test set ({HOLDOUT_IMDB_FULL}, {len(test_queries)} queries): "
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
        print(f"No test files (no path contains '{HOLDOUT_IMDB_FULL}').")


if __name__ == "__main__":
    main()
