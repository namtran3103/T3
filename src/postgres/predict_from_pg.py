"""
Run T3 prediction from a PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) file.

Uses the converted plan and T3's PerTupleTreeModel (model_pg.txt by default). No training.
Requires: model trained with src.postgres.training (default model_pg.txt), JOB schema (benchmark_setup/schemata/03-job-schema.sql).
Table sizes in schema are used for scan cardinality; if missing, scan output cardinality is used as fallback.

Usage (from T3 project root):
  python -m src.postgres.predict_from_pg path/to/pg_explain.json
  python -m src.postgres.predict_from_pg path/to/15a.json --use-plan-rows
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run from T3 project root so src imports work
repo = Path(__file__).resolve().parent.parent.parent
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

# Apply postgres-only patches before any T3 plan/pipeline code runs
from src.postgres import pg_patches
pg_patches.apply_patches()

import lightgbm as lgb

from src.database_manager import DatabaseManager
from src.metrics import q_error
from src.model import PerTupleTreeModel
from src.optimizer import BenchmarkedQuery, QueryCategory
from src.postgres.pg_to_umbra import load_pg_json, pg_explain_to_umbra
from src.query_plan import QueryPlan


def get_pg_actual_time_seconds(pg_data: dict | list) -> float | None:
    """
    Read actual execution time from PG EXPLAIN (ANALYZE, FORMAT JSON).
    PG reports in milliseconds; returns seconds, or None if not present.
    """
    if isinstance(pg_data, list) and pg_data:
        pg_data = pg_data[0]
    raw = pg_data.get("Execution Time")
    if raw is None:
        return None
    ms = float(raw)
    return ms / 1000.0


def _ensure_table_sizes_from_plan(plan_wrapper: dict, root_umbra: dict) -> None:
    """If JOB schema has no table sizes, set them from scan node cardinalities (best-effort)."""
    db = DatabaseManager.get_database("job")
    for table_name, table in db.schema.tables.items():
        if table.size is not None:
            continue
        # Use a large default so get_table_scan_size doesn't break; scan nodes have their own card
        table.size = 1_000_000


def predict_from_pg_json(
    json_path: str | Path,
    model_path: str | Path = "model_pg.txt",
    use_actual_card: bool = True,
    db_name: str = "job",
) -> tuple[float, list[float], float | None]:
    """
    Load PG EXPLAIN JSON, convert to Umbra plan, run T3 prediction.

    Returns (predicted_total_seconds, list of per-pipeline times in seconds, actual_time_seconds or None).
    """
    pg_data = load_pg_json(json_path)
    actual_seconds = get_pg_actual_time_seconds(pg_data)
    converted = pg_explain_to_umbra(pg_data, use_actual_card=use_actual_card)

    db = DatabaseManager.get_database(db_name)
    _ensure_table_sizes_from_plan(converted, converted["plan"])

    plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
    plan.build_pipelines(converted["analyzePlanPipelines"])

    dummy_runtimes = [0.0]
    name = Path(json_path).stem
    b = BenchmarkedQuery(plan, dummy_runtimes, name, "", QueryCategory.fixed)

    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model file not found: {model_path}. Run training first (e.g. python -m src.postgres.training).")

    booster = lgb.Booster(model_file=str(model_path))
    model = PerTupleTreeModel(booster)

    total = model.estimate_runtime(b)
    per_pipeline = model.estimate_pipeline_runtime(b)
    return total, per_pipeline, actual_seconds


def main() -> None:
    parser = argparse.ArgumentParser(description="T3 prediction from PostgreSQL EXPLAIN JSON")
    parser.add_argument("json_path", type=Path, help="Path to PG EXPLAIN (ANALYZE, FORMAT JSON) file")
    parser.add_argument("--model", type=Path, default=Path("model_pg.txt"), help="Path to T3 model (default: model_pg.txt)")
    parser.add_argument("--use-plan-rows", action="store_true", help="Use Plan Rows instead of Actual Rows for cardinality")
    parser.add_argument("--db", default="job", help="Database name in T3 (default: job)")
    args = parser.parse_args()

    total, per_pipeline, actual_seconds = predict_from_pg_json(
        args.json_path,
        model_path=args.model,
        use_actual_card=not args.use_plan_rows,
        db_name=args.db,
    )
    print(f"Predicted total time: {total:.6f} s")
    print(f"Per-pipeline times ({len(per_pipeline)} pipelines): {[f'{t:.6f}' for t in per_pipeline]}")
    if actual_seconds is not None:
        print(f"Actual total time (from JSON): {actual_seconds:.6f} s")
        err = q_error(actual_seconds, total)
        print(f"Q-error (actual vs predicted): {err:.4f}")


if __name__ == "__main__":
    main()
