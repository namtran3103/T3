"""
Run holdout training for every benchmark: train on all except one, test on that one.

All models are saved with versioning (base name or _v1, _v2, ...; no overwrite).
Each run's test summary is appended to holdout.txt (no overwrite).
For imdb_full: calls training_zeroshot_imdb_full_holdout. For others: calls
training_zeroshot_tpch_holdout with --holdout <name> and --out model_zero_holdout_<name>.txt.

Usage (from T3 project root):
  python -m src.zeroshot.run_all_holdouts
  python -m src.zeroshot.run_all_holdouts --data /path/to/parsed_plans
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

# Hardcoded list of holdout names (benchmark folders under parsed_plans)
PARSED_PLANS_ROOT = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
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
        description="Run holdout training for each benchmark (train on rest, test on one)."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(PARSED_PLANS_ROOT),
        help=f"Root directory containing benchmark subdirs (default: {PARSED_PLANS_ROOT})",
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

    holdout_txt = _repo / "holdout.txt"
    for i, holdout in enumerate(HOLDOUTS):
        model_name = f"model_zero_holdout_{holdout}.txt"
        if holdout == "imdb_full":
            cmd = [
                sys.executable,
                "-m",
                "src.zeroshot.training_zeroshot_imdb_full_holdout",
                "--data",
                str(data_dir),
            ]
            print(f"[{i + 1}/{len(HOLDOUTS)}] holdout={holdout} -> (imdb_full script, versioned output)")
        else:
            cmd = [
                sys.executable,
                "-m",
                "src.zeroshot.training_zeroshot_tpch_holdout",
                "--data",
                str(data_dir),
                "--holdout",
                holdout,
                "--out",
                model_name,
            ]
            print(f"[{i + 1}/{len(HOLDOUTS)}] holdout={holdout} -> {model_name}")
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
