"""
Train T3 on zero-shot RAW plans with imdb_full held out as test set.

Uses raw data (zero-shot-data/runs/raw): query_list with analyze_plans as EXPLAIN (ANALYZE) text.
Parses text to tree, maps PG operators, computes cardinalities/selectivities, then converts to T3
via zeroshot_raw_to_t3 and trains like training_zeroshot_imdb_full_holdout.

Use as many queries as possible from raw (more queries than parsed_plans). After training,
appends to diagnostics_training.txt: per-file stats and for each skipped query the reason
(no runtime or exception message).

Usage (from T3 project root):
  python -m src.zeroshot.training_raw_holdout_imdb_full
  python -m src.zeroshot.training_raw_holdout_imdb_full --data /path/to/raw
  python -m src.zeroshot.training_raw_holdout_imdb_full --trees 500
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
from src.metrics import q_error
from src.optimizer import BenchmarkedQuery, QueryCategory
from src.query_plan import QueryPlan
from src.zeroshot.training_zeroshot_tpch_holdout import (
    train_per_tuple_model,
    split_train_test_by_holdout,
    SEED,
)
from src.zeroshot.zeroshot_raw_to_t3 import (
    collect_all_raw_jsons,
    get_minimal_database,
    load_raw_json,
    raw_plan_to_t3,
    _flatten_plan_lines,
)

logger = logging.getLogger(__name__)


def _pipeline_span_seconds(t3_plan: dict) -> float:
    """Total span of pipeline times (max stop - min start) in seconds. Returns 0 if empty."""
    pipes = t3_plan.get("analyzePlanPipelines") or []
    if not pipes:
        return 0.0
    all_starts = [p["start"] for p in pipes]
    all_stops = [p["stop"] for p in pipes]
    span_us = max(all_stops) - min(all_starts)
    return max(0.0, span_us / 1e6)


DIAGNOSTICS_FILE = "diagnostics_training.txt"
HOLDOUT_IMDB_FULL = "imdb_full"
DEFAULT_MODEL_PATH = "model_raw_holdout_imdb_full.txt"
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/raw"

# Match zero-shot-cost-estimation parse_plans (parse_plan.py): min_runtime=100 ms, max_runtime=30000 ms.
# They do NOT filter by pipeline span; we do not either, so we keep the same plans (and can use more raw data).
MIN_RUNTIME_SEC = 0.1    # 100 ms
MAX_RUNTIME_SEC = 30.0   # 30 s
# Disabled: zero-shot has no pipeline-span check. Our get_pipeline_runtimes() corrects to sum to total_time.
MAX_PIPELINE_SPAN_Q_ERROR = None  # None = do not skip by span (match zero-shot; use more plans)


def load_benchmarked_queries_from_raw(
    json_paths: list[Path],
    use_actual_card: bool = True,
) -> list[BenchmarkedQuery]:
    """Build BenchmarkedQuery list from raw zero-shot JSON paths. One query per analyze_plan."""
    db = get_minimal_database()
    queries: list[BenchmarkedQuery] = []
    for jf in json_paths:
        try:
            data = load_raw_json(jf)
        except Exception as e:
            logger.warning("Failed to load file %s: %s", jf, e, exc_info=True)
            continue
        query_list = data.get("query_list", [])
        for idx, q in enumerate(query_list):
            if not q.get("analyze_plans"):
                continue
            lines = _flatten_plan_lines(q["analyze_plans"])
            if not lines:
                continue
            try:
                converted = raw_plan_to_t3(lines, use_actual_card=use_actual_card)
                if converted is None:
                    continue
                runtime_sec = converted.get("plan_runtime_seconds")
                if runtime_sec is None or runtime_sec <= 0:
                    continue
                if not (MIN_RUNTIME_SEC <= runtime_sec <= MAX_RUNTIME_SEC):
                    continue
                span_s = _pipeline_span_seconds(converted)
                if MAX_PIPELINE_SPAN_Q_ERROR is not None and span_s > 1e-9 and q_error(runtime_sec, span_s) > MAX_PIPELINE_SPAN_Q_ERROR:
                    continue
                plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
                plan.build_pipelines(converted["analyzePlanPipelines"])
                name = f"{jf.stem}_{idx}"
                b = BenchmarkedQuery(plan, [runtime_sec], name, "", QueryCategory.fixed, plan_dict=converted)
                queries.append(b)
            except Exception:
                continue
    return queries


def load_benchmarked_queries_from_raw_for_eval(
    json_paths: list[Path],
    use_actual_card: bool = True,
) -> list[BenchmarkedQuery]:
    """Like load_benchmarked_queries_from_raw but without runtime/span filters. Use for eval so all convertible plans load."""
    db = get_minimal_database()
    queries: list[BenchmarkedQuery] = []
    for jf in json_paths:
        try:
            data = load_raw_json(jf)
        except Exception as e:
            logger.warning("Failed to load file %s: %s", jf, e, exc_info=True)
            continue
        query_list = data.get("query_list", [])
        for idx, q in enumerate(query_list):
            if not q.get("analyze_plans"):
                continue
            lines = _flatten_plan_lines(q["analyze_plans"])
            if not lines:
                continue
            try:
                converted = raw_plan_to_t3(lines, use_actual_card=use_actual_card)
                if converted is None:
                    continue
                runtime_sec = converted.get("plan_runtime_seconds")
                if runtime_sec is None or runtime_sec <= 0:
                    continue
                plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
                plan.build_pipelines(converted["analyzePlanPipelines"])
                name = f"{jf.stem}_{idx}"
                b = BenchmarkedQuery(plan, [runtime_sec], name, "", QueryCategory.fixed, plan_dict=converted)
                queries.append(b)
            except Exception:
                continue
    return queries


def load_benchmarked_queries_from_raw_with_diagnostics(
    json_paths: list[Path],
    use_actual_card: bool = True,
) -> tuple[list[BenchmarkedQuery], list[dict]]:
    """
    Build BenchmarkedQuery list from raw JSON paths and return per-file diagnostics.
    Each diagnostic dict: path, plans_total, added, skip_no_runtime, skip_runtime_out_of_range,
    skip_span_inconsistent, skip_exception, file_error (optional). Only per-file summaries, no per-query reasons.
    Matches zero-shot parse_plans: 0.1s <= runtime <= 30s; no pipeline-span filter (zero-shot has none).
    """
    db = get_minimal_database()
    queries: list[BenchmarkedQuery] = []
    diagnostics: list[dict] = []
    for jf in json_paths:
        skip_no_runtime = 0
        skip_runtime_out_of_range = 0
        skip_span_inconsistent = 0
        skip_exception = 0
        added_this_file = 0
        plans_total = 0
        file_error: str | None = None
        try:
            data = load_raw_json(jf)
            query_list = data.get("query_list", [])
            for idx, q in enumerate(query_list):
                if not q.get("analyze_plans"):
                    continue
                lines = _flatten_plan_lines(q["analyze_plans"])
                if not lines:
                    continue
                plans_total += 1
                try:
                    converted = raw_plan_to_t3(lines, use_actual_card=use_actual_card)
                    if converted is None:
                        skip_exception += 1
                        continue
                    runtime_sec = converted.get("plan_runtime_seconds")
                    if runtime_sec is None or runtime_sec <= 0:
                        skip_no_runtime += 1
                        continue
                    if not (MIN_RUNTIME_SEC <= runtime_sec <= MAX_RUNTIME_SEC):
                        skip_runtime_out_of_range += 1
                        continue
                    span_s = _pipeline_span_seconds(converted)
                    if MAX_PIPELINE_SPAN_Q_ERROR is not None and span_s > 1e-9 and q_error(runtime_sec, span_s) > MAX_PIPELINE_SPAN_Q_ERROR:
                        skip_span_inconsistent += 1
                        continue
                    plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
                    plan.build_pipelines(converted["analyzePlanPipelines"])
                    name = f"{jf.stem}_{idx}"
                    b = BenchmarkedQuery(plan, [runtime_sec], name, "", QueryCategory.fixed, plan_dict=converted)
                    queries.append(b)
                    added_this_file += 1
                except Exception as e:
                    skip_exception += 1
                    logger.warning(
                        "Skipping plan %s_%s: %s",
                        jf.stem,
                        idx,
                        e,
                        exc_info=True,
                    )
            if skip_no_runtime or skip_runtime_out_of_range or skip_span_inconsistent or skip_exception:
                logger.info(
                    "Loaded %s from %s: %s ok, skip no_runtime=%s out_of_range=%s span_inconsistent=%s exception=%s",
                    jf.name,
                    added_this_file,
                    skip_no_runtime,
                    skip_runtime_out_of_range,
                    skip_span_inconsistent,
                    skip_exception,
                )
        except Exception as e:
            file_error = f"{type(e).__name__}: {e}"
            logger.warning("Failed to load file %s: %s", jf, e, exc_info=True)
        diagnostics.append({
            "path": str(jf),
            "plans_total": plans_total,
            "added": added_this_file,
            "skip_no_runtime": skip_no_runtime,
            "skip_runtime_out_of_range": skip_runtime_out_of_range,
            "skip_span_inconsistent": skip_span_inconsistent,
            "skip_exception": skip_exception,
            "file_error": file_error,
        })
    return queries, diagnostics


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
    data_source: str = "raw",
) -> None:
    """Append training diagnostics to diagnostics_training.txt; include skipped queries and exceptions."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = _repo / DIAGNOSTICS_FILE
    lines = [
        "",
        "---",
        f"timestamp={ts}",
        f"data_source={data_source}",
        f"holdout={holdout}",
        f"train_files={len(diagnostics)}",
        f"total_queries_used={total_queries}",
        "",
    ]
    total_plans = 0
    total_added = 0
    total_skip_no_runtime = 0
    total_skip_runtime_out_of_range = 0
    total_skip_span_inconsistent = 0
    total_skip_exception = 0
    files_failed = 0
    for d in diagnostics:
        total_plans += d["plans_total"]
        total_added += d["added"]
        total_skip_no_runtime += d["skip_no_runtime"]
        total_skip_runtime_out_of_range += d.get("skip_runtime_out_of_range", 0)
        total_skip_span_inconsistent += d.get("skip_span_inconsistent", 0)
        total_skip_exception += d["skip_exception"]
        if d.get("file_error"):
            files_failed += 1
        status = "ok" if d["added"] == d["plans_total"] and not d.get("file_error") else "skipped_some"
        line = (
            f"  {d['path']}: plans={d['plans_total']} added={d['added']} "
            f"skip_no_runtime={d['skip_no_runtime']} skip_out_of_range={d.get('skip_runtime_out_of_range', 0)} "
            f"skip_span_inconsistent={d.get('skip_span_inconsistent', 0)} skip_exception={d['skip_exception']}"
        )
        if d.get("file_error"):
            line += f" file_error={d['file_error']!r}"
        line += f" [{status}]"
        lines.append(line)
    lines.extend([
        "",
        f"total_plans={total_plans} total_added={total_added} "
        f"skip_no_runtime={total_skip_no_runtime} skip_out_of_range={total_skip_runtime_out_of_range} "
        f"skip_span_inconsistent={total_skip_span_inconsistent} skip_exception={total_skip_exception} "
        f"files_failed={files_failed}",
        "",
    ])
    with open(out_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Training diagnostics appended to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train T3 on zero-shot RAW plans with imdb_full held out as test set."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(DEFAULT_DATA_DIR),
        help=f"Root directory containing raw zero-shot JSON files (default: {DEFAULT_DATA_DIR})",
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
    parser.add_argument(
        "--trees",
        type=int,
        default=200,
        metavar="N",
        help="Number of trees (boosting rounds) to train (default: 200)",
    )
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_raw_jsons(data_dir)
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

    train_queries, train_diagnostics = load_benchmarked_queries_from_raw_with_diagnostics(
        train_paths
    )
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train benchmarks (plans)")

    _append_training_diagnostics(
        holdout=HOLDOUT_IMDB_FULL,
        diagnostics=train_diagnostics,
        total_queries=len(train_queries),
        data_source="raw",
    )

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet, num_trees=args.trees
    )

    base_out = args.out if args.out is not None else Path(DEFAULT_MODEL_PATH)
    out_path = next_available_model_path(_repo, base_out)
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if not args.no_eval and test_paths:
        test_queries = load_benchmarked_queries_from_raw(test_paths)
        if test_queries:
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                errors.append(q_error(actual, pred))
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
