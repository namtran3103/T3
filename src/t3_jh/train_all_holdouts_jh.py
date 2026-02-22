"""
Train one model per holdout: for each benchmark in HOLDOUTS, run training_jh_holdout
(train on all other data, test on that benchmark). Uses the same holdout list as
run_full_benchmark_jh. Models saved as model_jh_holdout_<name>.txt (versioned if exists).
Results appended to holdout_jh.txt and diagnostics to diagnostics_training_jh.txt.

Usage (from T3 repo root):
  python -m src.t3_jh.train_all_holdouts_jh
  python -m src.t3_jh.train_all_holdouts_jh --data /path/to/parsed_plans --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.t3_jh.run_full_benchmark_jh import HOLDOUTS, PARSED_PLANS_ROOT


def main():
    parser = argparse.ArgumentParser(
        description="Train T3 (Johannes) for each holdout: train on rest, test on one."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(PARSED_PLANS_ROOT),
        help="Root directory containing benchmark subdirs (parsed_plans)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print commands, do not run")
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
        ret = subprocess.run(
            cmd,
            cwd=str(_repo),
            env={**__import__("os").environ, "PYTHONPATH": str(_repo)},
        )
        if ret.returncode != 0:
            print(f"  Failed with exit code {ret.returncode}")
            sys.exit(ret.returncode)

    print(f"All results appended to {_repo / 'holdout_jh.txt'}")
    print("Done.")


if __name__ == "__main__":
    main()
