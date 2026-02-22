"""
Run full benchmark evaluation: for each holdout, train (train on rest, test on one),
then evaluate and append min/max/avg/p50/p75/p90 to holdout_jh.txt. Models saved with
versioned names (model_jh_holdout_<name>_vN.txt). Same usage pattern as zeroshot run_all_holdouts.

Usage (from T3 repo root, PYTHONPATH=src):
  python -m t3_jh.run_full_benchmark_jh
  python -m t3_jh.run_full_benchmark_jh --data /path/to/parsed_plans --dry-run
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
HOLDOUTS = [
    "accidents", "airline", "baseball", "basketball", "carcinogenesis", "consumer",
    "credit", "employee", "fhnk", "financial", "geneea", "genome", "hepatitis",
    "imdb", "imdb_full", "movielens", "seznam", "ssb", "tournament", "tpc_h", "walmart",
]


def main():
    parser = argparse.ArgumentParser(
        description="Run holdout training and eval for each benchmark (Johannes pipeline)."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(PARSED_PLANS_ROOT),
        help="Root directory containing benchmark subdirs",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print commands")
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir() and not args.dry_run:
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    for i, holdout in enumerate(HOLDOUTS):
        model_name = f"model_jh_holdout_{holdout}.txt"
        cmd = [
            sys.executable,
            "-m", "src.t3_jh.training_jh_holdout",
            "--data", str(data_dir),
            "--holdout", holdout,
            "--out", model_name,
        ]
        print(f"[{i + 1}/{len(HOLDOUTS)}] holdout={holdout} -> {model_name}")
        if args.dry_run:
            print("  ", " ".join(cmd))
            continue
        ret = subprocess.run(cmd, cwd=str(_repo), env={**__import__("os").environ, "PYTHONPATH": str(_repo)})
        if ret.returncode != 0:
            print(f"  Failed with exit code {ret.returncode}")
            sys.exit(ret.returncode)

    print(f"All results appended to {_repo / 'holdout_jh.txt'}")
    print("Done.")


if __name__ == "__main__":
    main()
