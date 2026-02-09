"""
Run few-shot finetuning for every zero-shot holdout model.

For each holdout: loads model_zero_holdout_<name>.txt, finetunes on up to N queries
(default 50) evenly distributed over that holdout's JSON files (seed 42), saves
model_zero_holdout_<name>_fewshot.txt (or ..._fewshot_<N>.txt if N != 50), and appends
test summary to holdout_fewshot.txt (or holdout_fewshot_<N>.txt if N != 50).
Clears that results file at start so it ends up with all holdouts' results in order.

Usage (from T3 project root):
  python -m src.zeroshot.run_all_holdouts_fewshot
  python -m src.zeroshot.run_all_holdouts_fewshot --data /path/to/parsed_plans --num-queries 100
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

PARSED_PLANS_ROOT = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
DEFAULT_NUM_QUERIES = 50
HOLDOUTS = [
    "accidents",
    "airline",
    "baseball",
    "basketball",
    "carcinogenesis",
    "consumer",
    "credit",
    "employee",
    "fhnk",
    "financial",
    "geneea",
    "genome",
    "hepatitis",
    "imdb",
    "imdb_full",
    "movielens",
    "seznam",
    "ssb",
    "tournament",
    "tpc_h",
    "walmart",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run few-shot finetuning for each zero-shot holdout model."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(PARSED_PLANS_ROOT),
        help=f"Root directory containing benchmark subdirs (default: {PARSED_PLANS_ROOT})",
    )
    parser.add_argument(
        "--num-queries",
        type=int,
        default=DEFAULT_NUM_QUERIES,
        help=f"Max queries per holdout for finetuning (default: {DEFAULT_NUM_QUERIES})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print commands, do not run",
    )
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir() and not args.dry_run:
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    if args.num_queries == DEFAULT_NUM_QUERIES:
        holdout_txt = _repo / "holdout_fewshot.txt"
    else:
        holdout_txt = _repo / f"holdout_fewshot_{args.num_queries}.txt"
    if not args.dry_run and holdout_txt.exists():
        holdout_txt.write_text("", encoding="utf-8")
        print(f"Cleared {holdout_txt} for appending.")

    for i, holdout in enumerate(HOLDOUTS):
        if args.num_queries == DEFAULT_NUM_QUERIES:
            model_out = f"model_zero_holdout_{holdout}_fewshot.txt"
        else:
            model_out = f"model_zero_holdout_{holdout}_fewshot_{args.num_queries}.txt"
        cmd = [
            sys.executable,
            "-m",
            "src.zeroshot.training_zeroshot_holdout_fewshot",
            "--data",
            str(data_dir),
            "--holdout",
            holdout,
            "--num-queries",
            str(args.num_queries),
            "--out",
            model_out,
        ]
        print(f"[{i + 1}/{len(HOLDOUTS)}] holdout={holdout} -> {model_out}")
        if args.dry_run:
            print("  ", " ".join(cmd))
            continue
        ret = subprocess.run(cmd, cwd=str(_repo))
        if ret.returncode != 0:
            print(f"  Failed with exit code {ret.returncode}")
            sys.exit(ret.returncode)
    if not args.dry_run:
        print(f"All results appended to {holdout_txt}")
    print("Done.")


if __name__ == "__main__":
    main()
