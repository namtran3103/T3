"""
Evaluate JOB full zero-shot JSON only (job_full_c8220.json in imdb_full) with the holdout model.

Loads model_zero_holdout_imdb_full.txt, runs only on job_full_c8220.json, prints and writes
all per-sample results plus summary to job_zero_t3_results.txt.

Usage (from T3 project root):
  python -m src.zeroshot.eval_imdb_full
  python -m src.zeroshot.eval_imdb_full --data /path/to/parsed_plans/imdb_full --out job_zero_t3_results.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb

from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.zeroshot.training_zeroshot_tpch_holdout import load_benchmarked_queries_from_zeroshot

IMDB_FULL_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/imdb_full"
JOB_FULL_JSON = "job_full_c8220.json"
MODEL_IMDB_FULL = "model_zero_holdout_imdb_full.txt"
OUTPUT_FILE = "job_zero_t3_results.txt"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate imdb_full plans with model_zero_holdout_imdb_full."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(IMDB_FULL_DIR),
        help=f"Directory containing job_full JSON (default: {IMDB_FULL_DIR})",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(MODEL_IMDB_FULL),
        help=f"Path to holdout model (default: {MODEL_IMDB_FULL})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(OUTPUT_FILE),
        help=f"Output file for results (default: {OUTPUT_FILE})",
    )
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    job_full_path = data_dir / JOB_FULL_JSON
    if not job_full_path.is_file():
        print(f"Error: {JOB_FULL_JSON} not found in {data_dir}")
        sys.exit(1)
    json_paths = [job_full_path]

    model_path = args.model if args.model.is_absolute() else _repo / args.model
    if not model_path.is_file():
        print(f"Error: model file not found: {model_path}")
        sys.exit(1)

    queries = load_benchmarked_queries_from_zeroshot(json_paths)
    if not queries:
        print("Error: no queries could be loaded.")
        sys.exit(1)

    booster = lgb.Booster(model_file=str(model_path))
    model = PerTupleTreeModel(booster)

    lines: list[str] = []
    errors: list[float] = []

    for b in queries:
        pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        err = q_error(actual, pred)
        errors.append(err)
        line = f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}"
        print(line)
        lines.append(line)

    summary = (
        f"Test set (job_full, {len(queries)} queries): "
        f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} "
        f"p90={np.percentile(errors, 90):.4f} min={min(errors):.4f} max={max(errors):.4f}"
    )
    print(summary)
    lines.append("")
    lines.append(summary)

    out_path = args.out if args.out.is_absolute() else _repo / args.out
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
