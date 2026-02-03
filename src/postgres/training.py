"""
Train T3 per-tuple tree model on PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) data.

Loads plans from pg_explain_job/, converts to Umbra-style, and trains like the main
repo (optimize_per_tuple_tree_model) with an 80/20 split by query template (seed 42)
so variants of the same JOB query stay in one set. Saves to model_pg.txt by default; predict_from_pg and predict_all_pg use that file by default.

Requires: lightgbm, sklearn, and project deps (see requirements.txt). JOB schema
(benchmark_setup/schemata/03-job-schema.sql) is used for table metadata.

Usage (from T3 project root):
  python -m src.postgres.training
  python -m src.postgres.training --out model_custom.txt --no-eval
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Run from T3 project root so src imports work
_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.postgres import pg_patches

pg_patches.apply_patches()

import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split

from src.database_manager import DatabaseManager
from src.model import FeatureMapper, PerTupleTreeModel
from src.optimizer import BenchmarkedQuery, QueryCategory
from src.postgres.pg_to_umbra import load_pg_json, pg_explain_to_umbra
from src.query_plan import QueryPlan


# Default folder with PG EXPLAIN JSONs (next to this file)
PG_EXPLAIN_JOB_DIR = Path(__file__).resolve().parent / "pg_explain_job"

TRAIN_TEST_SEED = 42
TRAIN_FRACTION = 0.8


def get_pg_actual_time_seconds(pg_data: dict | list) -> float | None:
    """Execution time in seconds from PG EXPLAIN JSON, or None if missing."""
    if isinstance(pg_data, list) and pg_data:
        pg_data = pg_data[0]
    raw = pg_data.get("Execution Time")
    if raw is None:
        return None
    return float(raw) / 1000.0


def _ensure_table_sizes_from_plan(plan_wrapper: dict, root_umbra: dict) -> None:
    """If JOB schema has no table sizes, set from scan cardinalities (best-effort)."""
    db = DatabaseManager.get_database("job")
    for table_name, table in db.schema.tables.items():
        if table.size is not None:
            continue
        table.size = 1_000_000


def _query_template(name: str) -> str:
    """JOB file name like '1a.json' or '33c.json' -> template '1' or '33'."""
    base = Path(name).stem
    m = re.match(r"^(\d+)", base)
    return m.group(1) if m else base


def load_benchmarked_queries(
    json_paths: list[Path], db_name: str = "job", use_actual_card: bool = True
) -> list[BenchmarkedQuery]:
    """Build BenchmarkedQuery list from PG EXPLAIN JSON paths. Skips files that fail."""
    db = DatabaseManager.get_database(db_name)
    queries: list[BenchmarkedQuery] = []
    for jf in json_paths:
        try:
            pg_data = load_pg_json(jf)
            actual_seconds = get_pg_actual_time_seconds(pg_data)
            if actual_seconds is None:
                continue
            converted = pg_explain_to_umbra(pg_data, use_actual_card=use_actual_card)
            _ensure_table_sizes_from_plan(converted, converted["plan"])
            plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
            plan.build_pipelines(converted["analyzePlanPipelines"])
            name = jf.stem
            b = BenchmarkedQuery(plan, [actual_seconds], name, "", QueryCategory.fixed)
            queries.append(b)
        except Exception:
            continue
    return queries


def split_paths_by_template(
    paths: list[Path], seed: int = TRAIN_TEST_SEED, train_fraction: float = TRAIN_FRACTION
) -> tuple[list[Path], list[Path]]:
    """Split paths into train/test by query template (e.g. all '1a','1b' in same set)."""
    by_template: dict[str, list[Path]] = {}
    for p in paths:
        t = _query_template(p.name)
        by_template.setdefault(t, []).append(p)
    templates = sorted(by_template.keys(), key=lambda x: int(x) if x.isdigit() else 0)
    train_t, test_t = train_test_split(
        templates, train_size=train_fraction, random_state=seed
    )
    train_paths = [p for t in train_t for p in by_template[t]]
    test_paths = [p for t in test_t for p in by_template[t]]
    return train_paths, test_paths


def train_per_tuple_model(
    queries: list[BenchmarkedQuery],
    seed: int = TRAIN_TEST_SEED,
    verbose: bool = True,
) -> PerTupleTreeModel:
    """Same logic as optimizer.optimize_per_tuple_tree_model but with configurable seed."""
    feature_mapper = FeatureMapper()
    x_vectors = []
    y_values = []
    for query in queries:
        for x, y in query.get_per_tuple_pipeline_runtime_data(feature_mapper):
            if np.any(x != 0):
                x_vectors.append(x)
                y_values.append(y)
    if not x_vectors:
        raise ValueError("No pipeline rows with non-zero features. Check PG plans and conversions.")
    x = np.vstack(x_vectors)
    y = np.array(y_values)
    y = np.maximum(y, 1e-15)
    y = -np.log(y)
    x_train, x_val, y_train, y_val = train_test_split(
        x, y, test_size=0.2, random_state=seed
    )
    param = {"objective": "mape", "verbose": 2 if verbose else -1}
    train_data = lgb.Dataset(
        x_train, label=y_train, feature_name=FeatureMapper.get_names(), params=param
    )
    val_data = lgb.Dataset(x_val, label=y_val, reference=train_data, params=param)
    bst = lgb.Booster(param, train_data)
    bst.add_valid(val_data, "val_data")
    if verbose:
        print("Initial:", bst.eval_train(), bst.eval_valid())
    for i in range(200):
        bst.update()
        if verbose and (i + 1) % 50 == 0:
            print(i + 1, bst.eval_train(), bst.eval_valid())
    if verbose:
        print("Final:", bst.eval_train(), bst.eval_valid())
    return PerTupleTreeModel(bst), bst


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train T3 model on PostgreSQL EXPLAIN JSON (JOB) plans."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=PG_EXPLAIN_JOB_DIR,
        help="Folder containing PG EXPLAIN (ANALYZE, FORMAT JSON) .json files",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("model_pg.txt"),
        help="Output model path (default: model_pg.txt)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=TRAIN_TEST_SEED,
        help="Random seed for train/test split (default: 42)",
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
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)
    paths = sorted(data_dir.glob("*.json"))
    if not paths:
        print(f"No .json files in {data_dir}")
        sys.exit(1)

    train_paths, test_paths = split_paths_by_template(
        paths, seed=args.seed, train_fraction=TRAIN_FRACTION
    )
    print(f"Train: {len(train_paths)} files ({len(set(_query_template(p.name) for p in train_paths))} templates)")
    print(f"Test:  {len(test_paths)} files ({len(set(_query_template(p.name) for p in test_paths))} templates)")

    train_queries = load_benchmarked_queries(train_paths)
    if not train_queries:
        print("Error: no train queries could be loaded.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train benchmarks")

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet
    )
    out_path = args.out if args.out.is_absolute() else _repo / args.out
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if not args.no_eval and test_paths:
        test_queries = load_benchmarked_queries(test_paths)
        if test_queries:
            from src.metrics import q_error
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                errors.append(q_error(actual, pred))
            print(f"Test set ({len(test_queries)} queries): q-error min={min(errors):.4f} median={np.median(errors):.4f} max={max(errors):.4f}")


if __name__ == "__main__":
    main()
