"""
Train T3 per-tuple tree model on JOB extended (augmented) PostgreSQL plans.

Uses 80/20 train/test split (seed 42). Saves to model_job_extended.txt. Plans are
loaded from pg_explain_job/extended/ and converted with pg_to_umbra (extended
format: actual_scan_in_card, component_selectivity, ius when present).

Requires: lightgbm, sklearn, and project deps. Database: job.

Usage (from T3 project root):
  python -m src.postgres.training_job_extended
  python -m src.postgres.training_job_extended --out my_model.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
from src.metrics import q_error
from src.optimizer import BenchmarkedQuery, QueryCategory
from src.postgres.pg_to_umbra import load_pg_json, pg_explain_to_umbra
from src.query_plan import QueryPlan


# JOB extended plans directory
PG_EXPLAIN_JOB_EXTENDED_DIR = Path(__file__).resolve().parent / "pg_explain_job" / "extended"

SEED = 42
TRAIN_FRACTION = 0.8
DEFAULT_MODEL_PATH = "model_job_extended.txt"
DB_NAME = "job"


def get_pg_actual_time_seconds(pg_data: dict | list) -> float | None:
    """Execution time in seconds from PG EXPLAIN JSON, or None if missing."""
    if isinstance(pg_data, list) and pg_data:
        pg_data = pg_data[0]
    raw = pg_data.get("Execution Time")
    if raw is None:
        return None
    return float(raw) / 1000.0


def _ensure_table_sizes_from_plan(plan_wrapper: dict, root_umbra: dict, db_name: str) -> None:
    """If schema has no table sizes, set from scan cardinalities (best-effort)."""
    db = DatabaseManager.get_database(db_name)
    for table_name, table in db.schema.tables.items():
        if table.size is not None:
            continue
        table.size = 1_000_000


def load_benchmarked_queries(
    json_paths: list[Path], db_name: str = DB_NAME, use_actual_card: bool = True
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
            _ensure_table_sizes_from_plan(converted, converted["plan"], db_name)
            plan = QueryPlan(converted, db, predicted_cardinalities=not use_actual_card)
            plan.build_pipelines(converted["analyzePlanPipelines"])
            name = jf.stem
            b = BenchmarkedQuery(plan, [actual_seconds], name, "", QueryCategory.fixed)
            queries.append(b)
        except Exception:
            continue
    return queries


def train_per_tuple_model(
    queries: list[BenchmarkedQuery],
    seed: int = SEED,
    verbose: bool = True,
) -> tuple[PerTupleTreeModel, lgb.Booster]:
    """Train per-tuple tree model on pipeline feature vectors."""
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
        description="Train T3 on JOB extended plans (80/20 split, seed 42)."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=PG_EXPLAIN_JOB_EXTENDED_DIR,
        help="Folder containing extended PG EXPLAIN JSON files",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(DEFAULT_MODEL_PATH),
        help=f"Output model path (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for 80/20 split (default: {SEED})",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=TRAIN_FRACTION,
        help=f"Fraction of data for training (default: {TRAIN_FRACTION})",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DB_NAME,
        help=f"Database name (default: {DB_NAME})",
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

    rng = np.random.default_rng(args.seed)
    indices = rng.permutation(len(paths))
    shuffled = [paths[i] for i in indices]
    n_train = int(round(len(shuffled) * args.train_fraction))
    n_train = max(1, min(n_train, len(shuffled) - 1))
    train_paths = shuffled[:n_train]
    test_paths = shuffled[n_train:]

    print(f"Train: {len(train_paths)} files ({100 * len(train_paths) / len(paths):.0f}%)")
    print(f"Test:  {len(test_paths)} files")

    train_queries = load_benchmarked_queries(train_paths, db_name=args.db)
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
        test_queries = load_benchmarked_queries(test_paths, db_name=args.db)
        if test_queries:
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)
                actual = b.get_total_runtime()
                errors.append(q_error(actual, pred))
            print(
                f"Test set ({len(test_queries)} queries): "
                f"q-error min={min(errors):.4f} median={np.median(errors):.4f} max={max(errors):.4f}"
            )


if __name__ == "__main__":
    main()
