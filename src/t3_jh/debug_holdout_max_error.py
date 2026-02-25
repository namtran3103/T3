"""
Debug script: find the highest q-error test queries for a holdout and dump their feature
vectors (and optionally compare to zeroshot model / feature vector).

Use this to track down why holdout has very high errors on some queries: inspect feature
vectors and compare with zeroshot predictions/features for the same plan.

Usage (from T3 repo root, PYTHONPATH=. or repo root):
  python -m src.t3_jh.debug_holdout_max_error --holdout tpc_h
  python -m src.t3_jh.debug_holdout_max_error --holdout walmart --top 20 --out debug_walmart.md
  python -m src.t3_jh.debug_holdout_max_error --holdout tpc_h --zeroshot-model model_zero_holdout_tpc_h.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import lightgbm as lgb

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.metrics import q_error

from .jh_dataloader import load_parsed_plans_from_json, collect_all_jsons
from .training_jh_holdout import split_train_test_by_holdout
from .jh_features import FeatureMapper
from .jh_model import PerTupleTreeModel

DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"


def _format_feature_vector(vec: np.ndarray, names: list[str], nonzero_only: bool = True) -> list[str]:
    lines = []
    for i, (n, v) in enumerate(zip(names, vec)):
        if nonzero_only and (v == 0 or (isinstance(v, float) and abs(v) < 1e-12)):
            continue
        lines.append(f"    {i}: {n} = {v}")
    if not lines and nonzero_only:
        lines.append("    (all zeros)")
    return lines


def _try_load_zeroshot_query(path: Path, plan_idx: int):
    """Load a single plan from a JSON using zeroshot pipeline; return (query, feature_matrix) or (None, None)."""
    try:
        from src.model import PerTupleTreeModel as ZSPerTupleTreeModel
        from src.optimizer import BenchmarkedQuery as ZSBenchmarkedQuery
        from src.optimizer import QueryCategory
        from src.zeroshot.zeroshot_to_t3 import (
            get_minimal_database,
            load_zeroshot_json,
            zeroshot_plan_to_t3,
        )
        from src.query_plan import QueryPlan as ZSQueryPlan
    except Exception as e:
        return None, None, str(e)
    try:
        data = load_zeroshot_json(path)
        plans = data.get("parsed_plans", [])
        if plan_idx >= len(plans):
            return None, None, f"plan_index {plan_idx} >= len(plans) {len(plans)}"
        zs_plan = plans[plan_idx]
        converted = zeroshot_plan_to_t3(zs_plan, use_actual_card=True)
        runtime_sec = converted.get("plan_runtime_seconds")
        if runtime_sec is None or runtime_sec <= 0:
            return None, None, "no or invalid plan_runtime_seconds"
        db = get_minimal_database()
        plan = ZSQueryPlan(converted, db, predicted_cardinalities=False)
        plan.build_pipelines(converted["analyzePlanPipelines"])
        from src.features import FeatureMapper as ZSFeatureMapper
        fm = ZSFeatureMapper()
        bq = ZSBenchmarkedQuery(plan, [runtime_sec], f"{path.stem}_{plan_idx}", "", QueryCategory.fixed)
        x = bq.get_feature_matrix(fm)
        return bq, x, None
    except Exception as e:
        return None, None, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Find highest q-error test queries for a holdout and dump feature vectors for debugging."
    )
    parser.add_argument("--holdout", type=str, required=True, help="Holdout benchmark name (e.g. tpc_h, walmart)")
    parser.add_argument("--data", type=Path, default=Path(DEFAULT_DATA_DIR), help="Root directory for parsed_plans")
    parser.add_argument(
        "--holdout-model",
        type=Path,
        default=None,
        help="Path to holdout model (default: model_jh_holdout_<holdout>.txt in repo)",
    )
    parser.add_argument(
        "--zeroshot-model",
        type=Path,
        default=None,
        help="Optional: path to zeroshot model to compare predictions; also tries to dump zeroshot feature vector for same plan",
    )
    parser.add_argument("--top", type=int, default=10, help="Number of worst-error queries to dump (default: 10)")
    parser.add_argument("--out", type=Path, default=None, help="Output report path (default: debug_holdout_<holdout>.md)")
    parser.add_argument("--quiet", action="store_true", help="Less stdout")
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    holdout_model_path = args.holdout_model
    if holdout_model_path is None:
        holdout_model_path = _repo / f"model_jh_holdout_{args.holdout}.txt"
    else:
        holdout_model_path = (holdout_model_path if holdout_model_path.is_absolute() else _repo / holdout_model_path).resolve()
    if not holdout_model_path.exists():
        print(f"Holdout model not found: {holdout_model_path}")
        sys.exit(1)

    all_paths = collect_all_jsons(data_dir)
    train_paths, test_paths = split_train_test_by_holdout(all_paths, args.holdout)
    if not test_paths:
        print(f"No test files for holdout '{args.holdout}'.")
        sys.exit(1)

    queries, diag = load_parsed_plans_from_json(test_paths)
    if not queries:
        print("No test queries loaded.")
        sys.exit(1)

    bst = lgb.Booster(model_file=str(holdout_model_path))
    model = PerTupleTreeModel(bst)
    fm = model.get_feature_mapper()
    names = FeatureMapper.get_names()

    errors = []
    preds = []
    for b in queries:
        pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        if pred <= 0:
            pred = 1e-9
        err = q_error(actual, pred)
        errors.append(err)
        preds.append(pred)
    errors = np.array(errors)
    preds = np.array(preds)
    actuals = np.array([b.get_total_runtime() for b in queries])

    order = np.argsort(errors)[::-1]
    top_k = min(args.top, len(queries))
    top_indices = order[:top_k]

    zs_model = None
    zs_fm = None
    zs_names = None
    if args.zeroshot_model:
        zs_path = args.zeroshot_model.resolve() if args.zeroshot_model.is_absolute() else _repo / args.zeroshot_model
        if zs_path.exists():
            try:
                zs_bst = lgb.Booster(model_file=str(zs_path))
                from src.model import PerTupleTreeModel as ZSPerTupleTreeModel
                zs_model = ZSPerTupleTreeModel(zs_bst)
                from src.features import FeatureMapper as ZSFeatureMapper
                zs_fm = ZSFeatureMapper()
                zs_names = zs_fm.get_names()
            except Exception as e:
                if not args.quiet:
                    print(f"Warning: could not load zeroshot model: {e}")
                zs_model = None

    out_path = args.out
    if out_path is None:
        out_path = _repo / f"debug_holdout_{args.holdout}.md"
    else:
        out_path = (out_path if out_path.is_absolute() else _repo / out_path).resolve()

    lines = [
        f"# Holdout max-error debug: {args.holdout}",
        "",
        f"Holdout model: `{holdout_model_path.name}`",
        f"Test queries: {len(queries)}",
        f"Top-{top_k} highest q-error queries.",
        "",
    ]
    if zs_model:
        lines.append(f"Zeroshot model: `{zs_path.name}` (for comparison).")
        lines.append("")

    for rank, qi in enumerate(top_indices, start=1):
        b = queries[qi]
        actual = actuals[qi]
        pred = preds[qi]
        err = errors[qi]
        lines.append(f"## Rank {rank}: {b.name} (q_error = {err:.4f})")
        lines.append("")
        lines.append(f"- **actual** = {actual:.6f} s")
        lines.append(f"- **pred (holdout)** = {pred:.6f} s")
        lines.append(f"- **q_error** = {err:.4f}")
        if b.source_path:
            lines.append(f"- **source** = `{b.source_path}` plan_index = {b.plan_index}")
        lines.append("")

        x = b.get_feature_matrix(fm)
        scan_sizes = fm.get_pipeline_scan_sizes(b.query_plan)
        pred_pipeline = model.estimate_pipeline_runtime(b)
        actual_pipeline = b.get_pipeline_runtimes()

        lines.append("### Per-pipeline (JH holdout)")
        lines.append("")
        for i in range(x.shape[0]):
            lines.append(f"#### Pipeline {i}")
            lines.append(f"- scan_size = {scan_sizes[i]}")
            lines.append(f"- actual runtime = {actual_pipeline[i]:.6f} s")
            lines.append(f"- pred runtime = {pred_pipeline[i]:.6f} s")
            lines.append("Feature vector (non-zero):")
            lines.extend(_format_feature_vector(x[i], names))
            lines.append("")
        lines.append("")

        if zs_model and b.source_path is not None and b.plan_index is not None:
            zs_bq, zs_x, zs_err = _try_load_zeroshot_query(Path(b.source_path), b.plan_index)
            if zs_bq is not None and zs_x is not None:
                zs_pred = zs_model.estimate_runtime(zs_bq)
                zs_err_q = q_error(actual, zs_pred) if zs_pred > 0 else float("nan")
                lines.append("### Zeroshot comparison (same plan, zeroshot pipeline)")
                lines.append("")
                lines.append(f"- **pred (zeroshot)** = {zs_pred:.6f} s")
                lines.append(f"- **q_error (zeroshot)** = {zs_err_q:.4f}")
                lines.append("")
                if zs_x.shape[0] == x.shape[0]:
                    for i in range(zs_x.shape[0]):
                        lines.append(f"#### Zeroshot pipeline {i} features (non-zero):")
                        if i < zs_x.shape[0]:
                            row = zs_x[i] if len(zs_x.shape) > 1 else zs_x
                            lines.extend(_format_feature_vector(row, zs_names))
                        lines.append("")
                else:
                    lines.append(f"(Zeroshot has {zs_x.shape[0]} pipelines vs JH {x.shape[0]} — pipeline count differs.)")
                    lines.append("Zeroshot feature vector (first row, non-zero):")
                    if len(zs_x.shape) > 1:
                        lines.extend(_format_feature_vector(zs_x[0], zs_names))
                    else:
                        lines.extend(_format_feature_vector(zs_x, zs_names))
                    lines.append("")
            elif not args.quiet and zs_err:
                lines.append("### Zeroshot comparison")
                lines.append(f"(Could not load same plan with zeroshot: {zs_err})")
                lines.append("")

    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Wrote report to {out_path}")
    if not args.quiet:
        print(f"Top error: {errors[order[0]]:.4f} ({queries[order[0]].name})")


if __name__ == "__main__":
    main()
