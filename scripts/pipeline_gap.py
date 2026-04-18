"""
Show the gap between raw (before-correction) pipeline runtimes and the
ground-truth plan_runtime for N zeroshot PostgreSQL plans.

Usage (from T3 project root, inside conda t3 env):
  python scripts/pipeline_gap.py
  python scripts/pipeline_gap.py --file /path/to/parsed_plans/tpc_h/workload_100k_s1_c8220.json --n 5
  python scripts/pipeline_gap.py --file /path/to/parsed_plans/tpc_h/workload_100k_s1_c8220.json --plan-idx 3 --n 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo))

from src.zeroshot.zeroshot_to_t3 import load_zeroshot_json, zeroshot_plan_to_t3
from src.zeroshot.training_zeroshot_tpch_holdout import load_benchmarked_queries_from_zeroshot

DEFAULT_FILE = "/Users/namtran/Downloads/zero-shot-data/runs/parsed_plans/tpc_h/workload_100k_s1_c8220.json"


def pipeline_gap(json_path: Path, plan_idx: int, bqs_by_name: dict) -> None:
    data = load_zeroshot_json(json_path)
    plans = data.get("parsed_plans", [])
    if plan_idx >= len(plans):
        print(f"  [skipped: file only has {len(plans)} plans]")
        return

    zs_plan = plans[plan_idx]
    if zs_plan.get("plan_runtime") is None or float(zs_plan["plan_runtime"]) <= 0:
        print(f"  [skipped: no valid plan_runtime]")
        return

    plan_runtime_s = float(zs_plan["plan_runtime"]) / 1000.0  # ms → s
    converted = zeroshot_plan_to_t3(zs_plan, use_actual_card=True)
    pipes_raw = converted["analyzePlanPipelines"]

    # Resolve BenchmarkedQuery for operator names
    name = f"{json_path.stem}_{plan_idx}" if len(plans) > 1 else json_path.stem
    bq = bqs_by_name.get(name)
    plan_pipelines = bq.query_plan.pipelines if bq else None

    # Raw times (pre-correction)
    all_starts = [p["start"] for p in pipes_raw]
    all_stops  = [p["stop"]  for p in pipes_raw]
    min_start  = min(all_starts)
    max_stop   = max(all_stops)
    analyze_plan_runtime_s = (max_stop - min_start) / 1_000_000

    raw_times = []
    for p in pipes_raw:
        span = p["stop"] - p["start"]
        raw = (span / (analyze_plan_runtime_s * 1_000_000)) * plan_runtime_s if analyze_plan_runtime_s > 0 else 0.0
        raw_times.append(raw)

    raw_sum    = sum(raw_times)
    correction = plan_runtime_s / raw_sum if raw_sum > 0 else float("inf")
    gap_s      = abs(raw_sum - plan_runtime_s)
    gap_pct    = gap_s / plan_runtime_s * 100 if plan_runtime_s > 0 else float("nan")
    zero_pipes = sum(1 for r in raw_times if r == 0)

    # ── Print ─────────────────────────────────────────────────────────────────
    print(f"\n{'='*82}")
    print(f"  {json_path.name}  [plan index {plan_idx}]")
    print(f"{'='*82}")
    print(f"  plan_runtime (ground truth):        {plan_runtime_s:.6f} s")
    print(f"  analyze_plan_runtime (recon. span): {analyze_plan_runtime_s:.6f} s")
    print()

    hdr = f"  {'Pipe':<5}  {'Operators':<32}  {'start µs':>11}  {'stop µs':>11}  {'span µs':>9}  {'RAW (s)':>10}  {'corrected (s)':>13}"
    sep = "  " + "─" * (len(hdr) - 2)
    print(hdr)
    print(sep)

    for i, (p_raw, raw) in enumerate(zip(pipes_raw, raw_times)):
        span      = p_raw["stop"] - p_raw["start"]
        corrected = raw * correction
        if plan_pipelines and i < len(plan_pipelines):
            ops = ", ".join(dict.fromkeys(ep.operator.operator_name for ep in plan_pipelines[i].operators))
        else:
            ops = str(p_raw["operators"])
        ops = ops[:32]
        print(f"  P{i:<4}  {ops:<32}  {p_raw['start']:>11.0f}  {p_raw['stop']:>11.0f}  {span:>9.0f}  {raw:>10.6f}  {corrected:>13.6f}")

    print(sep)
    print(f"  {'SUM':<5}  {'':32}  {'':>11}  {'':>11}  {'':>9}  {raw_sum:>10.6f}  {plan_runtime_s:>13.6f}")
    print()
    print(f"  Gap BEFORE correction : {gap_s:.6f} s  ({gap_pct:.1f}%)")
    print(f"  Correction factor     : {correction:.6f}")
    print(f"  Pipelines with 0 span : {zero_pipes} / {len(raw_times)}"
          + ("  ← sub-ms nodes rounded to 0" if zero_pipes else ""))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show pre-correction pipeline runtime gap for N zeroshot plans."
    )
    parser.add_argument("--file", type=Path, default=Path(DEFAULT_FILE),
                        help=f"Path to a parsed_plans JSON file (default: {DEFAULT_FILE})")
    parser.add_argument("--plan-idx", type=int, default=0,
                        help="Starting plan index within the file (default: 0)")
    parser.add_argument("--n", type=int, default=5,
                        help="Number of consecutive plans to show (default: 5)")
    args = parser.parse_args()

    if not args.file.is_file():
        print(f"Error: file not found: {args.file}")
        sys.exit(1)

    end_idx = args.plan_idx + args.n
    print(f"\nLoading plans {args.plan_idx}–{end_idx - 1} from {args.file.name} ...")
    bqs = load_benchmarked_queries_from_zeroshot([args.file], use_actual_card=True)
    bqs_by_name = {b.name: b for b in bqs}

    for idx in range(args.plan_idx, end_idx):
        pipeline_gap(args.file, idx, bqs_by_name)

    print()


if __name__ == "__main__":
    main()
