#!/usr/bin/env python3
"""
Find the query with the maximum q-error on the tpc_h test set and dump full investigation data:
feature vectors per pipeline, prediction errors per pipeline, scan sizes, etc.

Uses model_zero_holdout_tpc_h_v5.txt (or specified model) with the zeroshot pipeline.
Outputs a detailed report to stdout and optionally to a file.

Usage (from T3 project root):
  python find_max_qerror_query.py
  python find_max_qerror_query.py --model model_zero_holdout_tpc_h_v5.txt --data /path/to/parsed_plans
  python find_max_qerror_query.py --out max_error_report.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb

from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.pg_features import PgFeatureMapper
from src.zeroshot.training_zeroshot_tpch_holdout import (
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)
from src.zeroshot.training_zeroshot_tpch_holdout_ql import estimate_runtime_query_level
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons

DEFAULT_DATA_DIR = Path("/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans")
DEFAULT_MODEL = "model_zero_holdout_tpc_h_v5.txt"


def infer_test_set_from_model_path(model_path: Path) -> str | None:
    """Infer holdout name from model stem.

    Supports:
      - model_zero_holdout_<name>[_ql][_vN]  -> name  (e.g. model_zero_holdout_tpc_h_v5, model_zero_holdout_tpc_h_ql)
      - model_zero_<name>_holdout[_ql][_vN]  -> name  (e.g. model_zero_tpch_holdout_v2, model_zero_tpch_holdout_ql)
    """
    stem = model_path.stem
    stem = re.sub(r"_v\d+$", "", stem)
    stem = re.sub(r"_ql$", "", stem)

    # model_zero_holdout_<name>
    prefix1 = "model_zero_holdout_"
    if stem.startswith(prefix1):
        name = stem[len(prefix1):]
        return _normalize_holdout_name(name) or None

    # model_zero_<name>_holdout
    match = re.match(r"^model_zero_(.+)_holdout$", stem)
    if match:
        name = match.group(1)
        return _normalize_holdout_name(name) or None

    return None


def is_query_level_model(model_path: Path) -> bool:
    """Return True if the model filename contains the _ql suffix (after stripping version)."""
    stem = re.sub(r"_v\d+$", "", model_path.stem)
    return stem.endswith("_ql")


def _normalize_holdout_name(name: str) -> str:
    """Map common aliases to path holdout names (e.g. tpch -> tpc_h)."""
    aliases = {"tpch": "tpc_h", "tpcds": "tpc_ds"}
    return aliases.get(name.lower(), name)


def format_feature_vector(vec: np.ndarray, names: list[str], indent: str = "  ") -> list[str]:
    """Format feature vector with all names and values (including zeros)."""
    lines = []
    for i, (n, v) in enumerate(zip(names, vec)):
        lines.append(f"{indent}{i:2d}: {n} = {v}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find the query with max q-error and dump full investigation data."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=_repo / DEFAULT_MODEL,
        help=f"Path to model file (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Root directory for parsed_plans (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output file path (default: print to stdout only)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=1,
        help="Number of worst queries to dump (default: 1)",
    )
    parser.add_argument(
        "--query-level",
        action="store_true",
        default=None,
        help=(
            "Use query-level inference (sum pipeline features, predict once). "
            "Auto-detected from model name (_ql suffix) if not provided."
        ),
    )
    args = parser.parse_args()

    model_path = args.model if args.model.is_absolute() else _repo / args.model
    if not model_path.is_file():
        print(f"Error: model file not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    test_set = infer_test_set_from_model_path(model_path)
    if not test_set:
        print("Error: could not infer test set from model name.", file=sys.stderr)
        sys.exit(1)

    # Load test data
    all_paths = collect_all_zeroshot_jsons(data_dir)
    _, test_paths = split_train_test_by_holdout(all_paths, holdout_name=test_set)
    if not test_paths:
        print(f"No test paths for holdout '{test_set}'.", file=sys.stderr)
        sys.exit(1)

    queries = load_benchmarked_queries_from_zeroshot(test_paths)
    if not queries:
        print("No test queries loaded.", file=sys.stderr)
        sys.exit(1)

    # Auto-detect query-level from model name unless explicitly set
    use_query_level = args.query_level if args.query_level else is_query_level_model(model_path)

    # Load model with PgFeatureMapper (required for zeroshot models)
    fm = PgFeatureMapper()
    booster = lgb.Booster(model_file=str(model_path))
    model = PerTupleTreeModel(booster, feature_mapper=fm)
    feature_names = PgFeatureMapper.get_names()

    print(f"Mode: {'query-level' if use_query_level else 'per-pipeline'}")

    # Compute q-errors for all queries
    errors = []
    preds = []
    actuals = []
    for b in queries:
        if use_query_level:
            pred = estimate_runtime_query_level(booster, b, fm)
        else:
            pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        pred = max(1e-9, pred)
        err = q_error(actual, pred)
        errors.append(err)
        preds.append(pred)
        actuals.append(actual)

    errors = np.array(errors)
    preds = np.array(preds)
    actuals = np.array(actuals)

    # Sort by q-error descending
    order = np.argsort(errors)[::-1]
    top_k = min(args.top, len(queries))
    top_indices = order[:top_k]

    lines = [
        "=" * 80,
        "MAX Q-ERROR QUERY INVESTIGATION",
        "=" * 80,
        f"Model: {model_path.name}",
        f"Test set: {test_set}",
        f"Total queries: {len(queries)}",
        f"Q-error stats: min={min(errors):.4f} max={max(errors):.4f} avg={np.mean(errors):.4f} p50={np.median(errors):.4f}",
        "",
    ]

    for rank, qi in enumerate(top_indices, start=1):
        b = queries[qi]
        actual = actuals[qi]
        pred = preds[qi]
        err = errors[qi]

        lines.extend([
            "-" * 80,
            f"RANK {rank}: {b.name}",
            "-" * 80,
            "",
            "## Query-level summary",
            "",
            f"  actual runtime (s):     {actual:.6f}",
            f"  predicted runtime (s): {pred:.6f}",
            f"  q-error:                {err:.4f}",
            "",
        ])

        x = b.get_feature_matrix(fm)

        if use_query_level:
            # Collapse all pipelines into the single summed vector the model actually used
            x_sum = np.sum(x, axis=0)
            ql_raw = booster.predict(x_sum.reshape(1, -1)).flatten()[0]
            ql_pred = np.exp(-ql_raw)

            lines.extend([
                f"## Per-pipeline breakdown  ({x.shape[0]} pipeline(s) summed into one query-level vector)",
                "",
                "### Pipeline 0  [summed]",
                "",
                f"  pipelines summed:          {x.shape[0]}",
                f"  actual runtime (s):        {actual:.6f}",
                f"  predicted runtime (s):     {ql_pred:.6f}",
                "",
                f"  raw model output (log):    {ql_raw:.6f}",
                f"  per-tuple pred (exp(-x)):  {ql_pred:.6e}",
                "",
                "  Feature vector (all features):",
            ])
            lines.extend(format_feature_vector(x_sum, feature_names, indent="    "))
            lines.append("")
            lines.append("")
            lines.append("## Full feature matrix (all pipelines before summing)")
            lines.append("")
            for i in range(x.shape[0]):
                lines.append(f"  Pipeline {i}: " + " ".join(f"{v:.4g}" for v in x[i]))
            lines.append("")
        else:
            scan_sizes = fm.get_pipeline_scan_sizes(b.plan_dict) if b.plan_dict else np.ones(x.shape[0])
            actual_pipeline = b.get_pipeline_runtimes()
            pred_pipeline = model.estimate_pipeline_runtime(b)
            raw_log_pred = booster.predict(x).flatten()
            per_tuple_pred = np.exp(-raw_log_pred)

            lines.append("## Per-pipeline breakdown")
            lines.append("")

            for i in range(x.shape[0]):
                lines.append(f"### Pipeline {i}")
                lines.append("")
                if i < len(scan_sizes):
                    lines.append(f"  scan_size (act_card sum): {scan_sizes[i]:.2f}")
                if i < len(actual_pipeline):
                    lines.append(f"  actual runtime (s):       {actual_pipeline[i]:.6f}")
                if i < len(pred_pipeline):
                    lines.append(f"  predicted runtime (s):    {pred_pipeline[i]:.6f}")
                if i < len(actual_pipeline) and i < len(pred_pipeline) and actual_pipeline[i] > 0:
                    pipe_qerr = q_error(actual_pipeline[i], pred_pipeline[i])
                    pipe_abs_err = abs(actual_pipeline[i] - pred_pipeline[i])
                    lines.extend([
                        f"  pipeline q-error:         {pipe_qerr:.4f}",
                        f"  pipeline abs error (s):   {pipe_abs_err:.6f}",
                        "",
                    ])
                else:
                    lines.append("")
                if i < len(raw_log_pred):
                    lines.extend([
                        f"  raw model output (log):    {raw_log_pred[i]:.6f}",
                        f"  per-tuple pred (exp(-x)): {per_tuple_pred[i]:.6e}",
                        "",
                    ])
                lines.append("  Feature vector (all features):")
                lines.extend(format_feature_vector(x[i], feature_names, indent="    "))
                lines.append("")

            lines.append("")
            lines.append("## Full feature matrix (all pipelines)")
            lines.append("")
            for i in range(x.shape[0]):
                lines.append(f"  Pipeline {i}: " + " ".join(f"{v:.4g}" for v in x[i]))
            lines.append("")

    report = "\n".join(lines)

    if args.out:
        out_path = args.out if args.out.is_absolute() else _repo / args.out
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {out_path}")

    print(report)


if __name__ == "__main__":
    main()
