"""
Run query-level inference with estimated cardinalities for every holdout,
using the per-holdout model files listed in results/holdout_query_act.txt.

Appends one summary line per holdout to results/exact_train_est_eval.txt.

Usage (from T3 project root):
  python -m results.scripts.run_exact_train_est_eval
  python results/scripts/run_exact_train_est_eval.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

import numpy as np
import lightgbm as lgb

from src.metrics import q_error
from src.pg_features import PgFeatureMapper
from src.zeroshot.training_zeroshot_tpch_holdout import (
    DEFAULT_DATA_DIR,
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
)
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons
from src.zeroshot.training_zeroshot_tpch_holdout_ql import estimate_runtime_query_level

RESULTS_DIR = _repo / "results"
ACT_FILE    = RESULTS_DIR / "holdout_query_act.txt"
OUT_FILE    = RESULTS_DIR / "exact_train_est_eval.txt"
DATA_DIR    = Path(DEFAULT_DATA_DIR)

_LINE_RE = re.compile(
    r"Test set \((\w+),.*?model=([\w.]+)"
)


def parse_holdout_models(path: Path) -> dict[str, str]:
    """Return {holdout_name: model_filename} from holdout_query_act.txt."""
    mapping: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            m = _LINE_RE.search(line)
            if m:
                mapping[m.group(1)] = m.group(2)
    return mapping


def run_holdout(
    holdout: str,
    model_name: str,
    all_json_paths: list[Path],
    feature_mapper: PgFeatureMapper,
) -> str | None:
    model_path = _repo / model_name
    if not model_path.is_file():
        print(f"[SKIP] Model not found: {model_path}")
        return None

    _, test_paths = split_train_test_by_holdout(all_json_paths, holdout_name=holdout)
    if not test_paths:
        print(f"[SKIP] No test JSONs found for holdout '{holdout}'")
        return None

    queries = load_benchmarked_queries_from_zeroshot(
        test_paths, use_actual_card=False  # estimated cardinalities
    )
    if not queries:
        print(f"[SKIP] No queries loaded for holdout '{holdout}'")
        return None

    booster = lgb.Booster(model_file=str(model_path))

    errors: list[float] = []
    for b in queries:
        pred   = estimate_runtime_query_level(booster, b, feature_mapper)
        actual = b.get_total_runtime()
        errors.append(q_error(actual, pred))

    summary = (
        f"Test set ({holdout}, {len(queries)} queries) [query-level]: "
        f"q-error avg={np.mean(errors):.4f} "
        f"p50={np.median(errors):.4f} "
        f"p90={np.percentile(errors, 90):.4f} "
        f"min={min(errors):.4f} "
        f"max={max(errors):.4f} "
        f"model={model_name}"
    )
    print(summary)
    return summary


def main() -> None:
    if not ACT_FILE.is_file():
        print(f"Error: {ACT_FILE} not found")
        sys.exit(1)

    holdout_models = parse_holdout_models(ACT_FILE)
    if not holdout_models:
        print(f"Error: no holdout→model entries parsed from {ACT_FILE}")
        sys.exit(1)

    print(f"Found {len(holdout_models)} holdouts to evaluate:")
    for h, m in holdout_models.items():
        print(f"  {h:25s} -> {m}")

    if not DATA_DIR.is_dir():
        print(f"Error: data directory not found: {DATA_DIR}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(DATA_DIR)
    if not all_json_paths:
        print(f"Error: no JSON files under {DATA_DIR}")
        sys.exit(1)
    print(f"\nLoaded {len(all_json_paths)} JSON paths from {DATA_DIR}\n")

    feature_mapper = PgFeatureMapper()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as out_f:
        for holdout, model_name in holdout_models.items():
            print(f"\n--- {holdout} ---")
            summary = run_holdout(holdout, model_name, all_json_paths, feature_mapper)
            if summary:
                out_f.write(summary + "\n")

    print(f"\nDone. Results written to {OUT_FILE}")


if __name__ == "__main__":
    main()
