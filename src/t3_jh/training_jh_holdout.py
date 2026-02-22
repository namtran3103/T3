"""
Train T3 (Johannes pipeline) on parsed_plans with one benchmark held out as test.
Uses jh_dataloader and jh_model; appends diagnostics to diagnostics_training_jh.txt
and test summary (min/max/avg/p50/p75/p90) to holdout_jh.txt. Model names versioned (v1, v2, ...).

Usage (from T3 repo root, PYTHONPATH=. or default):
  python -m src.t3_jh.training_jh_holdout
  python -m src.t3_jh.training_jh_holdout --data /path/to/parsed_plans --holdout imdb_full --out model_jh_holdout.txt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from src.metrics import q_error

from .jh_dataloader import load_parsed_plans_from_json, collect_all_jsons
from .jh_features import FeatureMapper
from .jh_model import PerTupleTreeModel

SEED = 42
DEFAULT_DATA_DIR = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans"
DEFAULT_MODEL_PATH = "model_jh_holdout.txt"
DIAGNOSTICS_FILE = "diagnostics_training_jh.txt"
HOLDOUT_FILE = "holdout_jh.txt"


def next_available_model_path(repo: Path, base_path: Path) -> Path:
    resolved = base_path if base_path.is_absolute() else repo / base_path
    if not resolved.exists():
        return resolved
    stem, suffix = resolved.stem, resolved.suffix
    n = 1
    while True:
        candidate = resolved.parent / f"{stem}_v{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def append_diagnostics(holdout: str, diagnostics: list, total_queries: int, repo: Path) -> None:
    out_path = repo / DIAGNOSTICS_FILE
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "",
        "---",
        f"timestamp={ts}",
        f"holdout={holdout}",
        f"train_files={len(diagnostics)}",
        f"total_queries_used={total_queries}",
        "",
    ]
    for d in diagnostics:
        lines.append(
            f"  {d['path']}: plans={d['plans_total']} added={d['added']} "
            f"skip_runtime={d['skip_runtime']} skip_exception={d['skip_exception']}"
        )
    lines.append("")
    with open(out_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Diagnostics appended to {out_path}")


def split_train_test_by_holdout(all_paths: list, holdout_name: str):
    test_paths = [p for p in all_paths if holdout_name in p.parts]
    train_paths = [p for p in all_paths if p not in set(test_paths)]
    return train_paths, test_paths


def train_per_tuple_model(queries, seed=SEED, verbose=True, num_trees=200):
    feature_mapper = FeatureMapper()
    train_idx, val_idx = train_test_split(
        np.arange(len(queries)), test_size=0.2, random_state=seed
    )
    train_queries = [queries[i] for i in train_idx]
    val_queries = [queries[i] for i in val_idx]

    x_vectors = []
    y_values = []
    for q in train_queries:
        for x, y in q.get_per_tuple_pipeline_runtime_data(feature_mapper):
            if np.any(x != 0):
                x_vectors.append(x)
                y_values.append(y)
    if not x_vectors:
        raise ValueError("No pipeline rows with non-zero features.")
    x_train = np.vstack(x_vectors)
    y_train = np.array(y_values, dtype=float)
    y_train = np.maximum(y_train, 1e-15)
    y_train = -np.log(y_train)

    x_val_vec = []
    y_val_vec = []
    for q in val_queries:
        for x, y in q.get_per_tuple_pipeline_runtime_data(feature_mapper):
            if np.any(x != 0):
                x_val_vec.append(x)
                y_val_vec.append(y)
    x_val = np.vstack(x_val_vec) if x_val_vec else np.zeros((0, x_train.shape[1]))
    y_val = np.array(y_val_vec, dtype=float) if y_val_vec else np.array([])
    if len(y_val) > 0:
        y_val = np.maximum(y_val, 1e-15)
        y_val = -np.log(y_val)

    param = {"objective": "mape", "verbose": 2 if verbose else -1}
    train_data = lgb.Dataset(
        x_train, label=y_train, feature_name=FeatureMapper.get_names(), params=param
    )
    val_data = None
    if len(y_val) > 0 and x_val.shape[0] > 0:
        val_data = lgb.Dataset(x_val, label=y_val, reference=train_data, params=param)
    bst = lgb.Booster(param, train_data)
    if val_data is not None:
        bst.add_valid(val_data, "val")

    for _ in range(num_trees - 1):
        bst.update()

    return PerTupleTreeModel(bst), bst


def main():
    parser = argparse.ArgumentParser(
        description="Train T3 (Johannes) on parsed_plans with holdout."
    )
    parser.add_argument("--data", type=Path, default=Path(DEFAULT_DATA_DIR))
    parser.add_argument("--out", type=Path, default=Path(DEFAULT_MODEL_PATH))
    parser.add_argument("--holdout", type=str, default="imdb_full")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--no-eval", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Print detailed load diagnostics (per-file and sample errors)")
    args = parser.parse_args()

    data_dir = args.data.resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_paths = collect_all_jsons(data_dir)
    if not all_paths:
        print(f"No .json under {data_dir}")
        sys.exit(1)

    train_paths, test_paths = split_train_test_by_holdout(all_paths, args.holdout)
    if not train_paths:
        print(f"No train files (all contain '{args.holdout}').")
        sys.exit(1)

    print(f"Train: {len(train_paths)} files, Test: {len(test_paths)} files")

    train_queries, train_diag = load_parsed_plans_from_json(
        train_paths, verbose=args.verbose or True
    )

    # Always print per-file summary when we have diagnostics
    def _print_load_diagnostics(diag_list: list, label: str) -> None:
        print(f"\n--- {label} ---")
        total_plans = total_added = total_skip_rt = total_skip_ex = 0
        for d in diag_list:
            total_plans += d.get("plans_total", 0)
            total_added += d.get("added", 0)
            total_skip_rt += d.get("skip_runtime", 0)
            total_skip_ex += d.get("skip_exception", 0)
            path_short = Path(d["path"]).name
            line = (
                f"  {path_short}: plans={d.get('plans_total', 0)} added={d.get('added', 0)} "
                f"skip_runtime={d.get('skip_runtime', 0)} skip_exception={d.get('skip_exception', 0)}"
            )
            if d.get("skip_act_time_le_zero", 0):
                line += f" (act_time<=0: {d['skip_act_time_le_zero']})"
            if d.get("skip_runtime_validity", 0):
                line += f" (validity: {d['skip_runtime_validity']})"
            if d.get("file_error"):
                line += f" FILE_ERROR={d['file_error']!r}"
            print(line)
        print(f"  TOTAL: plans={total_plans} added={total_added} skip_runtime={total_skip_rt} skip_exception={total_skip_ex}")

        # Sample exceptions (first 20 across all files)
        all_ex = []
        for d in diag_list:
            for t in d.get("exceptions", []):
                all_ex.append((d.get("path", ""), t[0], t[1], t[2]))
        if all_ex:
            print(f"\n  Sample errors (first {min(20, len(all_ex))} of {len(all_ex)}):")
            for path, idx, kind, msg in all_ex[:20]:
                path_short = Path(path).name
                print(f"    [{path_short} plan_{idx}] {kind}: {msg[:120]}{'...' if len(msg) > 120 else ''}")
        print()

    _print_load_diagnostics(train_diag, "Train load diagnostics")

    if not train_queries:
        print("No train queries loaded. Fix errors above or adjust data/holdout.")
        sys.exit(1)
    print(f"Loaded {len(train_queries)} train queries")

    append_diagnostics(args.holdout, train_diag, len(train_queries), _repo)

    model, bst = train_per_tuple_model(
        train_queries, seed=args.seed, verbose=not args.quiet
    )
    out_path = next_available_model_path(_repo, args.out)
    bst.save_model(str(out_path))
    print(f"Saved model to {out_path}")

    if not args.no_eval and test_paths:
        test_queries, _ = load_parsed_plans_from_json(test_paths)
        if test_queries:
            errors = []
            for b in test_queries:
                pred = model.estimate_runtime(b)  # seconds (same as get_total_runtime)
                actual = b.get_total_runtime()
                if pred <= 0:
                    pred = 1e-9
                err = q_error(actual, pred)
                errors.append(err)
            errors = np.array(errors)
            summary = (
                f"holdout={args.holdout} n={len(test_queries)} "
                f"min={np.min(errors):.4f} max={np.max(errors):.4f} avg={np.mean(errors):.4f} "
                f"p50={np.percentile(errors, 50):.4f} p75={np.percentile(errors, 75):.4f} p90={np.percentile(errors, 90):.4f}"
            )
            print(summary)
            with open(_repo / HOLDOUT_FILE, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"Results appended to {_repo / HOLDOUT_FILE}")
        else:
            print("No test queries loaded.")
    elif not args.no_eval and not test_paths:
        print(f"No test files for holdout '{args.holdout}'.")


if __name__ == "__main__":
    main()
