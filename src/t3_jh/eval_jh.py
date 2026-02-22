"""
Evaluate a saved Johannes T3 model on parsed_plans JSONs. Reports min/max/avg/p50/p75/p90
q-error and appends to a results file.

By default runs only on imdb_full/job_full_c8220.json. Use --all to run on all JSONs under --data.

Usage (from T3 repo root):
  python -m src.t3_jh.eval_jh --model model_jh_holdout.txt
  python -m src.t3_jh.eval_jh --model model_jh_holdout.txt --all
  python -m src.t3_jh.eval_jh --model model_jh_holdout.txt --files imdb_full/job_full_c8220.json --out results_jh.txt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import lightgbm as lgb

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.metrics import q_error

from .jh_dataloader import load_parsed_plans_from_json, collect_all_jsons
from .jh_model import PerTupleTreeModel

DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
DEFAULT_EVAL_FILE = "imdb_full/job_full_c8220.json"
RESULTS_FILE = "results_jh.txt"


def main():
    parser = argparse.ArgumentParser(description="Evaluate Johannes T3 model on parsed_plans.")
    parser.add_argument("--model", type=Path, required=True, help="Path to saved .txt model")
    parser.add_argument("--data", type=Path, default=Path(DEFAULT_DATA_DIR), help="Root directory for parsed_plans")
    parser.add_argument("--out", type=Path, default=None, help=f"Append results here (default: repo/{RESULTS_FILE})")
    parser.add_argument("--files", type=str, nargs="*", help="JSON paths under --data to evaluate (default: " + DEFAULT_EVAL_FILE + ")")
    parser.add_argument("--all", action="store_true", help="Evaluate on all JSONs under --data (ignores --files)")
    parser.add_argument("--quiet", action="store_true", help="Only print summary, not per-query results")
    parser.add_argument("--write-per-query", action="store_true", help="Append one line per query to output file (name actual pred q_error)")
    args = parser.parse_args()

    model_path = args.model.resolve() if args.model.is_absolute() else _repo / args.model
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        sys.exit(1)

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Not a directory: {data_dir}")
        sys.exit(1)

    if args.all:
        json_paths = collect_all_jsons(data_dir)
    elif args.files:
        json_paths = [data_dir / f for f in args.files]
        json_paths = [p for p in json_paths if p.exists()]
    else:
        json_paths = [data_dir / DEFAULT_EVAL_FILE]
        json_paths = [p for p in json_paths if p.exists()]

    if not json_paths:
        print("No JSON files to evaluate.")
        sys.exit(1)

    print(f"Model: {model_path}")
    print(f"Data:  {len(json_paths)} file(s)")
    for p in json_paths:
        print(f"  - {p.relative_to(data_dir) if data_dir in p.parents else p}")

    bst = lgb.Booster(model_file=str(model_path))
    model = PerTupleTreeModel(bst)

    queries, diag = load_parsed_plans_from_json(json_paths, verbose=True)
    total_plans = sum(d.get("plans_total", 0) for d in diag)
    total_added = sum(d.get("added", 0) for d in diag)
    total_skip_rt = sum(d.get("skip_runtime", 0) for d in diag)
    total_skip_ex = sum(d.get("skip_exception", 0) for d in diag)
    print(f"\nLoad: {total_plans} plans in files -> {total_added} queries loaded (skip_runtime={total_skip_rt}, skip_exception={total_skip_ex})")
    for d in diag:
        if d.get("plans_total", 0) > 0:
            print(f"  {Path(d['path']).name}: plans={d['plans_total']} added={d['added']} skip_runtime={d.get('skip_runtime', 0)} skip_exception={d.get('skip_exception', 0)}")

    all_ex = []
    for d in diag:
        for t in d.get("exceptions", []):
            all_ex.append((Path(d["path"]).name, t[0], t[1], t[2]))
    if all_ex:
        n_show = min(20, len(all_ex))
        print(f"\n  Sample skip reasons (first {n_show} of {len(all_ex)}):")
        for path_name, idx, kind, msg in all_ex[:n_show]:
            msg_short = (msg[:100] + "...") if len(msg) > 100 else msg
            print(f"    [{path_name} plan_{idx}] {kind}: {msg_short}")

    if not queries:
        print("No queries loaded.")
        sys.exit(1)

    print(f"\nEvaluating {len(queries)} queries:\n")

    errors = []
    preds = []
    actuals = []
    for b in queries:
        pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        if pred <= 0:
            pred = 1e-9
        err = q_error(actual, pred)
        errors.append(err)
        preds.append(pred)
        actuals.append(actual)
        if not args.quiet:
            print(f"  {b.name}: actual={actual:.6f}s pred={pred:.6f}s q_error={err:.4f}")
    errors = np.array(errors)

    print()
    summary_line = (
        f"model={model_path.name} n={len(queries)} "
        f"min={np.min(errors):.4f} max={np.max(errors):.4f} avg={np.mean(errors):.4f} "
        f"p50={np.percentile(errors, 50):.4f} p75={np.percentile(errors, 75):.4f} p90={np.percentile(errors, 90):.4f}"
    )
    print("Summary: " + summary_line)

    out_path = args.out.resolve() if args.out and args.out.is_absolute() else (_repo / args.out if args.out else _repo / RESULTS_FILE)
    with open(out_path, "a", encoding="utf-8") as f:
        if args.write_per_query:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " model=" + model_path.name + "\n")
            for b, actual, pred, err in zip(queries, actuals, preds, errors):
                f.write(f"  {b.name} actual={actual:.6f} pred={pred:.6f} q_error={err:.4f}\n")
        f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + summary_line + "\n")
    print(f"Appended to {out_path}")


if __name__ == "__main__":
    main()
