"""
Run T3 prediction for all PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) files in a folder.

Usage (from T3 project root):
  python -m src.postgres.predict_all_pg /path/to/pg_explain_job
  python -m src.postgres.predict_all_pg /path/to/pg_explain_job --model model_pg.txt --db job
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __name__ == "__main__":
    repo = Path(__file__).resolve().parent.parent.parent
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

import numpy as np
from src.metrics import q_error
from src.postgres.predict_from_pg import predict_from_pg_json


def main() -> None:
    parser = argparse.ArgumentParser(description="T3 prediction for all PG EXPLAIN JSON files in a folder")
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing PG EXPLAIN (ANALYZE, FORMAT JSON) .json files",
    )
    parser.add_argument("--model", type=Path, default=Path("model_pg.txt"), help="Path to T3 model (default: model_pg.txt)")
    parser.add_argument("--use-plan-rows", action="store_true", help="Use Plan Rows instead of Actual Rows")
    parser.add_argument("--db", default="job", help="T3 database name")
    parser.add_argument("--quiet", action="store_true", help="Only print summary, not per-file lines")
    args = parser.parse_args()

    folder = args.folder.resolve()
    if not folder.is_dir():
        parser.error(f"Not a directory: {folder}")

    json_files = sorted(folder.glob("*.json"))
    if not json_files:
        print(f"No .json files in {folder}")
        return

    results: list[tuple[str, float, float | None, float | None]] = []
    for jf in json_files:
        name = jf.name
        try:
            pred, _, actual = predict_from_pg_json(
                jf,
                model_path=args.model,
                use_actual_card=not args.use_plan_rows,
                db_name=args.db,
            )
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            if not args.quiet:
                print(f"{name}: ERROR {err_msg}")
            results.append((name, 0.0, None, None))
            continue
        q = q_error(actual, pred) if actual is not None else None
        results.append((name, pred, actual, q))
        if not args.quiet:
            line = f"{name}: pred={pred:.6f}s"
            if actual is not None:
                line += f" actual={actual:.6f}s q_err={q:.4f}"
            print(line)

    # Summary
    with_actual = [(n, pred, actual, q) for n, pred, actual, q in results if actual is not None and q is not None]
    print(f"\nProcessed {len(results)} files ({len(with_actual)} with actual time).")
    if with_actual:
        q_errors = [r[3] for r in with_actual]
        print(f"Q-error: min={min(q_errors):.4f} p50={np.median(q_errors):.4f} p90={np.quantile(q_errors, 0.9):.4f} max={max(q_errors):.4f}")


if __name__ == "__main__":
    main()
