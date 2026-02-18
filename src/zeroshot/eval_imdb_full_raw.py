"""
Evaluate JOB full on imdb_full using **raw** zero-shot data and the raw holdout model.

Loads job_full_c8220.json from runs/raw/imdb_full, converts plans via zeroshot_raw_to_t3.
Eval uses all plans that convert and have runtime (no runtime/span filters). Uses
model_raw_holdout_imdb_full.txt. Prints only the summary; writes per-query results + summary
to job_full_raw_zero_t3_results.txt.

Usage (from T3 project root):
  python -m src.zeroshot.eval_imdb_full_raw
  python -m src.zeroshot.eval_imdb_full_raw --data /path/to/raw/imdb_full --model model_raw_holdout_imdb_full.txt --out job_full_raw_zero_t3_results.txt
  python -m src.zeroshot.eval_imdb_full_raw --diagnose
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
from src.zeroshot.training_raw_holdout_imdb_full import (
    load_benchmarked_queries_from_raw_for_eval,
    MIN_RUNTIME_SEC,
    MAX_RUNTIME_SEC,
    MAX_PIPELINE_SPAN_Q_ERROR,
    _pipeline_span_seconds,
)
from src.zeroshot.zeroshot_raw_to_t3 import (
    get_minimal_database,
    load_raw_json,
    raw_plan_to_t3,
    _flatten_plan_lines,
)
from src.query_plan import QueryPlan
IMDB_FULL_RAW_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/raw/imdb_full"
JOB_FULL_JSON = "job_full_c8220.json"
MODEL_RAW_IMDB_FULL = "model_raw_holdout_imdb_full.txt"
OUTPUT_FILE = "job_full_raw_zero_t3_results.txt"


def _run_diagnose(job_full_path: Path) -> None:
    """Load job_full raw JSON and report how many plans load or are skipped (per reason)."""
    data = load_raw_json(job_full_path)
    query_list = data.get("query_list", [])
    plans_with_analyze = sum(1 for q in query_list if q.get("analyze_plans"))
    print(f"File: {job_full_path.name} — {len(query_list)} queries, {plans_with_analyze} with analyze_plans")
    print("-" * 80)
    db = get_minimal_database()
    ok = 0
    skip_no_runtime = 0
    skip_out_of_range = 0
    skip_span_inconsistent = 0
    skip_exception = 0
    for idx, q in enumerate(query_list):
        if not q.get("analyze_plans"):
            continue
        lines = _flatten_plan_lines(q["analyze_plans"])
        if not lines:
            continue
        try:
            converted = raw_plan_to_t3(lines, use_actual_card=True)
            if converted is None:
                skip_exception += 1
                continue
            runtime_sec = converted.get("plan_runtime_seconds")
            if runtime_sec is None or runtime_sec <= 0:
                skip_no_runtime += 1
                continue
            if not (MIN_RUNTIME_SEC <= runtime_sec <= MAX_RUNTIME_SEC):
                skip_out_of_range += 1
                continue
            span_s = _pipeline_span_seconds(converted)
            if span_s > 1e-9 and q_error(runtime_sec, span_s) > MAX_PIPELINE_SPAN_Q_ERROR:
                skip_span_inconsistent += 1
                continue
            plan = QueryPlan(converted, db, predicted_cardinalities=False)
            plan.build_pipelines(converted["analyzePlanPipelines"])
            ok += 1
        except Exception:
            skip_exception += 1
    print(
        f"Summary: {ok} ok, skip_no_runtime={skip_no_runtime} skip_out_of_range={skip_out_of_range} "
        f"skip_span_inconsistent={skip_span_inconsistent} skip_exception={skip_exception}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate imdb_full JOB full (raw data) with model_raw_holdout_imdb_full."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(IMDB_FULL_RAW_DIR),
        help=f"Directory containing job_full raw JSON (default: {IMDB_FULL_RAW_DIR})",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(MODEL_RAW_IMDB_FULL),
        help=f"Path to raw holdout model (default: {MODEL_RAW_IMDB_FULL})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(OUTPUT_FILE),
        help=f"Output file for results (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Report load counts by skip reason (no model/eval).",
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

    if args.diagnose:
        _run_diagnose(job_full_path)
        return

    model_path = args.model if args.model.is_absolute() else _repo / args.model
    if not model_path.is_file():
        print(f"Error: model file not found: {model_path}")
        sys.exit(1)

    queries = load_benchmarked_queries_from_raw_for_eval(json_paths)
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
        lines.append(f"{b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")

    summary = (
        f"Test set (job_full raw, {len(queries)} queries): "
        f"q-error avg={np.mean(errors):.4f} p50={np.median(errors):.4f} p75={np.percentile(errors, 75):.4f} "
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
