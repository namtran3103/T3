"""
Run holdout training for every benchmark using DeepDB-augmented plans.

Uses runs/deepdb_augmented/ (parsed + DeepDB cardinalities). For each holdout:
train on all except one, test on that one. Models: model_zero_holdout_<name>_augmented.txt.
Results appended to holdout_augmented.txt (same schema as holdout.txt).

Usage (from T3 project root):
  python -m src.zeroshot.run_all_holdouts_augmented
  python -m src.zeroshot.run_all_holdouts_augmented --data /path/to/deepdb_augmented
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

# Holdouts present under deepdb_augmented (no imdb_full in that folder)
DEEPDB_AUGMENTED_ROOT = "/Users/namtran/Downloads/zero-shot-data/runs/deepdb_augmented"
HOLDOUTS_AUGMENTED = [
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
    "movielens",
    "seznam",
    "ssb",
    "tournament",
    "tpc_h",
    "walmart",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run holdout training for each benchmark (DeepDB-augmented data)."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(DEEPDB_AUGMENTED_ROOT),
        help=f"Root directory containing benchmark subdirs (default: {DEEPDB_AUGMENTED_ROOT})",
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

    holdout_txt = _repo / "holdout_augmented.txt"
    if not args.dry_run and holdout_txt.exists():
        holdout_txt.write_text("", encoding="utf-8")
        print(f"Cleared {holdout_txt} for appending.")

    for i, holdout in enumerate(HOLDOUTS_AUGMENTED):
        model_name = f"model_zero_holdout_{holdout}_augmented.txt"
        cmd = [
            sys.executable,
            "-m",
            "src.zeroshot.training_zeroshot_tpch_holdout_augmented",
            "--data",
            str(data_dir),
            "--holdout",
            holdout,
            "--out",
            model_name,
        ]
        print(f"[{i + 1}/{len(HOLDOUTS_AUGMENTED)}] holdout={holdout} -> {model_name}")
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
