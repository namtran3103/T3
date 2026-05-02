"""
Run holdout training for every benchmark: train on all except one, test on that one.

All models are saved with versioning (base name or _v1, _v2, ...; no overwrite).
Each run's test summary is appended to holdout.txt (no overwrite).
Calls training_zeroshot_tpch_holdout (per-pipeline) or training_zeroshot_tpch_holdout_ql
(query-level) with --holdout <name> and the appropriate --out model name.

Usage (from T3 project root):
  python -m src.zeroshot.run_all_holdouts
  python -m src.zeroshot.run_all_holdouts --data /path/to/parsed_plans
  python -m src.zeroshot.run_all_holdouts --query-level
  python -m src.zeroshot.run_all_holdouts --query-level --use-estimated-card
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
PARSED_PLANS_ROOT = _repo / "zero-shot-data" / "runs" / "parsed_plans"
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
        "--use-estimated-card",
        action="store_true",
        help="Use estimated cardinalities (est_card) instead of actual; same feature names, default is actual.",
    )
    parser.add_argument(
        "--query-level",
        action="store_true",
        help=(
            "Use query-level training (sum all per-pipeline feature vectors per query). "
            "Delegates to training_zeroshot_tpch_holdout_ql and names models "
            "model_zero_holdout_<name>_ql.txt."
        ),
    )
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    training_module = (
        "src.zeroshot.training_zeroshot_tpch_holdout_ql"
        if args.query_level
        else "src.zeroshot.training_zeroshot_tpch_holdout"
    )

    holdout_txt = _repo / "holdout.txt"
    for i, holdout in enumerate(HOLDOUTS):
        suffix = "_ql" if args.query_level else ""
        model_name = f"model_zero_holdout_{holdout}{suffix}.txt"
        cmd = [
            sys.executable,
            "-m",
            training_module,
            "--data",
            str(data_dir),
            "--holdout",
            holdout,
            "--out",
            model_name,
        ]
        print(f"[{i + 1}/{len(HOLDOUTS)}] holdout={holdout} -> {model_name}")
        if args.use_estimated_card:
            cmd.append("--use-estimated-card")
        ret = subprocess.run(cmd, cwd=str(_repo))
        if ret.returncode != 0:
            print(f"  Failed with exit code {ret.returncode}")
            sys.exit(ret.returncode)
    print(f"All results appended to {holdout_txt}")
    print("Done.")


if __name__ == "__main__":
    main()
