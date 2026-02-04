#!/usr/bin/env python3
"""
Run Umbra query prediction and print the feature vector for each pipeline.

Requires project dependencies: pip install -r requirements.txt

Usage:
  # From SQL file (requires Umbra server running):
  python -m testing.run_umbra_prediction queries/tpch/5.sql --server http://localhost:8080 --db tpchSf1

  # From existing Umbra plan JSON (no server needed):
  python -m testing.run_umbra_prediction --plan-json data/tpchSf1/fixed/tpchSf1_q5.json --db tpchSf1

  # With model prediction (optional):
  python -m testing.run_umbra_prediction queries/tpch/5.sql --server http://localhost:8080 --db tpchSf1 --model model.txt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.database_manager import DatabaseManager
from src.features import FeatureMapper
from src.optimizer import BenchmarkedQuery, QueryCategory
from src.query_plan import QueryPlan


def load_plan_from_json(path: Path, db_name: str) -> tuple[QueryPlan, list[float], str]:
    """Load Umbra plan from a benchmark JSON file (e.g. data/tpchSf1/fixed/tpchSf1_q5.json)."""
    with open(path) as f:
        data = json.load(f)
    # Structure: data["plan"]["plan"] = { "plan": root, "ius": [...], "analyzePlanPipelines": [...] }
    plan_wrapper = data["plan"]["plan"]
    db = DatabaseManager.get_database(db_name)
    plan = QueryPlan(plan_wrapper, db, predicted_cardinalities=False)
    plan.build_pipelines(plan_wrapper["analyzePlanPipelines"])
    runtimes = [b["executionTime"] for b in data["benchmarks"]]
    query_text = data["plan"].get("query_text", "")
    return plan, runtimes, query_text


def load_plan_from_server(sql_path: Path, server: str, db_name: str) -> tuple[QueryPlan, list[float], str]:
    """Get Umbra plan by running EXPLAIN on the server."""
    from src.benchmark import Benchmarker

    query_text = sql_path.read_text()
    db = DatabaseManager.get_database(db_name)
    benchmarker = Benchmarker(server)
    analyzed = benchmarker.analyze_query(db, query_text)
    # analyzed["plan"] = plan wrapper with "plan", "ius", "analyzePlanPipelines"
    plan_wrapper = analyzed["plan"]
    plan = QueryPlan(plan_wrapper, db, predicted_cardinalities=False)
    plan.build_pipelines(plan_wrapper["analyzePlanPipelines"])
    # No real runtimes when only analyzing; use dummy for feature extraction
    runtimes = [0.0]
    return plan, runtimes, query_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Umbra query prediction and print feature vectors per pipeline."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "sql_file",
        nargs="?",
        type=Path,
        help="Path to SQL file (e.g. queries/tpch/5.sql). Requires --server.",
    )
    group.add_argument(
        "--plan-json",
        type=Path,
        metavar="PATH",
        help="Path to existing Umbra plan JSON (e.g. data/tpchSf1/fixed/tpchSf1_q5.json).",
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8080",
        help="Umbra server URL (default: http://localhost:8080). Used when passing SQL file.",
    )
    parser.add_argument(
        "--db",
        default="tpchSf1",
        help="Database name (default: tpchSf1). Must match schema (tpchSf1 for tpch, etc.).",
    )
    parser.add_argument(
        "--model",
        type=Path,
        metavar="PATH",
        help="Optional path to model file (e.g. model.txt) to run pipeline runtime prediction.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print all feature dimensions; otherwise only non-zero.",
    )
    args = parser.parse_args()

    if args.plan_json is not None:
        plan, runtimes, query_text = load_plan_from_json(args.plan_json, args.db)
        name = args.plan_json.stem
    else:
        if args.sql_file is None:
            parser.error("Either pass sql_file or use --plan-json")
        plan, runtimes, query_text = load_plan_from_server(args.sql_file, args.server, args.db)
        name = args.sql_file.stem

    bq = BenchmarkedQuery(plan, runtimes, name, query_text, QueryCategory.fixed)
    mapper = FeatureMapper()
    feature_matrix = mapper.get_pipeline_estimation_matrix(plan)
    feature_names = mapper.get_names()

    print(f"Query: {name}")
    print(f"Pipelines: {len(plan.pipelines)}")
    print()

    for i, (pipeline, vec) in enumerate(zip(plan.pipelines, feature_matrix)):
        scan_card = pipeline.get_pipeline_scan_cardinality()
        print(f"--- Pipeline {i} (scan cardinality: {scan_card}) ---")
        for j, (fname, val) in enumerate(zip(feature_names, vec)):
            if args.verbose or val != 0:
                print(f"  {fname}: {val}")
        print()

    if args.model is not None and args.model.exists():
        import lightgbm as lgb
        from src.model import PerTupleTreeModel

        booster = lgb.Booster(model_file=str(args.model))
        model = PerTupleTreeModel(booster)
        total_pred = model.estimate_runtime(bq)
        per_pipeline_pred = model.estimate_pipeline_runtime(bq)
        print("--- Model predictions (Umbra model) ---")
        print(f"Total predicted runtime (s): {total_pred:.6f}")
        for i, t in enumerate(per_pipeline_pred):
            print(f"  Pipeline {i}: {t:.6f} s")
    elif args.model is not None:
        print(f"Warning: model file not found: {args.model}")


if __name__ == "__main__":
    main()
