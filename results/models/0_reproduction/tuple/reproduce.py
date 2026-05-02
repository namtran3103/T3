"""
Reproduce tuple-level holdout results for all benchmarks.

This variant replaces PgFeatureMapper.get_pipeline_scan_sizes with a Umbra-like
implementation that uses the actual scan cardinalities (sum of act_card per pipeline)
rather than constant 1.0.  The patch is applied before any training or inference.

For each holdout in HOLDOUTS, trains on all other benchmarks and evaluates on the holdout.
Runs both actual and estimated cardinality variants.

Models are saved as:
  act/<holdout>.txt  (actual cardinalities)
  est/<holdout>.txt  (estimated cardinalities)

Per-query q-errors are printed; the summary line (avg / p50 / p90) is appended to:
  act/0_results.txt
  est/0_results.txt

Re-running the script overwrites the model files and appends another result line.

Usage (from T3 project root):
  python results/models/0_reproduction/tuple/reproduce.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_script_dir = Path(__file__).resolve().parent
_repo = _script_dir.parent.parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

# Apply the tuple-level scan-size patch before any training/inference imports.
# patch_scan_sizes.py lives in the same directory; _script_dir is already in sys.path
# because that is where this script was found by the interpreter, but we make it
# explicit to be safe when the script is invoked from a different working directory.
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import patch_scan_sizes  # noqa: E402
patch_scan_sizes.apply_patch()

from src.metrics import q_error
from src.zeroshot.zeroshot_to_t3 import collect_all_zeroshot_jsons
from src.zeroshot.training_zeroshot_tpch_holdout import (
    SEED,
    load_benchmarked_queries_from_zeroshot,
    split_train_test_by_holdout,
    train_zeroshot_pipeline_lightgbm,
)

PARSED_PLANS_ROOT = _repo / "zero-shot-data" / "runs" / "parsed_plans"

HOLDOUTS = [
    "accidents",
    "airline",
    "baseball",
    "basketball",
    "carcinogenesis",
    "consumer",
    "credit",
    "employee",
    "fhnk",
    "financial",
    "geneea",
    "genome",
    "hepatitis",
    "imdb_full",
    "movielens",
    "seznam",
    "ssb",
    "tournament",
    "tpc_h",
    "walmart",
]


def run_holdout(
    holdout: str,
    card_dir: Path,
    all_json_paths: list[Path],
    use_actual_card: bool,
) -> None:
    card_label = "act" if use_actual_card else "est"
    print(f"\n=== holdout={holdout}  card={card_label} ===")

    train_paths, test_paths = split_train_test_by_holdout(all_json_paths, holdout)
    if not train_paths:
        print(f"  Skipping: no train paths after holding out {holdout}")
        return

    train_queries = load_benchmarked_queries_from_zeroshot(train_paths, use_actual_card=use_actual_card)
    if not train_queries:
        print("  Skipping: no train queries loaded")
        return
    print(f"  Train: {len(train_queries)} plans from {len(train_paths)} files")

    model, bst = train_zeroshot_pipeline_lightgbm(train_queries, seed=SEED)

    out_path = card_dir / f"{holdout}.txt"
    bst.save_model(str(out_path))
    print(f"  Model saved: {out_path.relative_to(_repo)}")

    if not test_paths:
        print(f"  No test files for {holdout}")
        return

    test_queries = load_benchmarked_queries_from_zeroshot(test_paths, use_actual_card=use_actual_card)
    if not test_queries:
        print(f"  No test queries loaded for {holdout}")
        return

    errors = []
    for b in test_queries:
        pred = model.estimate_runtime(b)
        actual = b.get_total_runtime()
        err = q_error(actual, pred)
        errors.append(err)
        print(f"  {b.name}: pred={pred:.6f}s actual={actual:.6f}s q_error={err:.4f}")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = (
        f"[{ts}] holdout={holdout} card={card_label} n={len(errors)}"
        f" avg={np.mean(errors):.4f} p50={np.median(errors):.4f}"
        f" p90={np.percentile(errors, 90):.4f} model={out_path.name}"
    )
    print(f"  {summary}")

    results_file = card_dir / "0_results.txt"
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(f"  Appended to {results_file.relative_to(_repo)}")


def main() -> None:
    data_dir = Path(PARSED_PLANS_ROOT).resolve()
    if not data_dir.is_dir():
        print(f"Error: not a directory: {data_dir}")
        sys.exit(1)

    all_json_paths = collect_all_zeroshot_jsons(data_dir)
    if not all_json_paths:
        print(f"No .json files under {data_dir}")
        sys.exit(1)
    print(f"Found {len(all_json_paths)} JSON files under {data_dir}")

    act_dir = _script_dir / "act"
    est_dir = _script_dir / "est"

    total = len(HOLDOUTS) * 2
    for i, holdout in enumerate(HOLDOUTS):
        print(f"\n[{i * 2 + 1}/{total}] act — {holdout}")
        run_holdout(holdout, act_dir, all_json_paths, use_actual_card=True)
        print(f"\n[{i * 2 + 2}/{total}] est — {holdout}")
        run_holdout(holdout, est_dir, all_json_paths, use_actual_card=False)

    print("\nDone. Results appended to act/0_results.txt and est/0_results.txt")


if __name__ == "__main__":
    main()
