"""
Evaluate the JOB benchmark (job_full_c8220.json) with query-level models trained
on imdb_full.

Two runs:
  act model + actual cardinalities  → appends to act_act.txt
  est model + estimated cardinalities → appends to est_est.txt

Output format matches src/zeroshot/eval_imdb_full.py:
  per-query: "{name}: pred={:.6f}s actual={:.6f}s q_error={:.4f}"
  summary:   "Test set (job_full, N queries): q-error avg=… p50=… p75=… p90=… min=… max=…"

Usage (from T3 project root):
  python results/job/eval_job_query_level.py
  python results/job/eval_job_query_level.py --data /path/to/parsed_plans/imdb_full
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
from src.pg_features import PgFeatureMapper
from src.zeroshot.training_zeroshot_tpch_holdout import load_benchmarked_queries_from_zeroshot
from src.zeroshot.training_zeroshot_tpch_holdout_ql import estimate_runtime_query_level

IMDB_FULL_DIR = _repo / "zero-shot-data" / "runs" / "parsed_plans" / "imdb_full"
JOB_FULL_JSON = "job_full_c8220.json"

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR.parent / "models" / "query-level"

RUNS = [
    {
        "label": "act+actual",
        "model": MODEL_DIR / "act" / "imdb_full.txt",
        "use_actual_card": True,
        "out": SCRIPT_DIR / "act_act.txt",
    },
    {
        "label": "est+estimated",
        "model": MODEL_DIR / "est" / "imdb_full.txt",
        "use_actual_card": False,
        "out": SCRIPT_DIR / "est_est.txt",
    },
]


def run_evaluation(
    queries,
    booster: lgb.Booster,
    feature_mapper: PgFeatureMapper,
    out_path: Path,
    label: str,
    model_path: Path,
) -> None:
    lines: list[str] = [f"model: {model_path}"]
    errors: list[float] = []

    for b in queries:
        pred = estimate_runtime_query_level(booster, b, feature_mapper)
        actual = b.get_total_runtime()
        err = q_error(actual, pred)
        errors.append(err)
        line = f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}"
        print(line)
        lines.append(line)

    summary = (
        f"Test set (job_full, {len(queries)} queries): "
        f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} "
        f"p75={np.percentile(errors, 75):.4f} "
        f"p90={np.percentile(errors, 90):.4f} "
        f"min={min(errors):.4f} max={max(errors):.4f}"
    )
    print(summary)
    lines.append("")
    lines.append(summary)

    with open(out_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[{label}] Appended results to {out_path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate JOB benchmark with query-level imdb_full models."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(IMDB_FULL_DIR),
        help=f"Directory containing {JOB_FULL_JSON} (default: {IMDB_FULL_DIR})",
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

    feature_mapper = PgFeatureMapper()

    for run in RUNS:
        label = run["label"]
        model_path: Path = run["model"]
        use_actual_card: bool = run["use_actual_card"]
        out_path: Path = run["out"]

        if not model_path.is_file():
            print(f"[{label}] Error: model not found: {model_path}")
            continue

        print(f"\n{'='*60}")
        print(f"Run: {label}")
        print(f"Model: {model_path}")
        print(f"Output: {out_path}")
        print(f"{'='*60}")

        queries = load_benchmarked_queries_from_zeroshot(
            [job_full_path], use_actual_card=use_actual_card
        )
        if not queries:
            print(f"[{label}] Error: no queries could be loaded.")
            continue

        booster = lgb.Booster(model_file=str(model_path))
        run_evaluation(queries, booster, feature_mapper, out_path, label, model_path)


if __name__ == "__main__":
    main()
