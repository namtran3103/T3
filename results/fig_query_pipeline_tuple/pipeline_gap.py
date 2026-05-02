"""
Show the gap between raw (before-correction) pipeline runtimes and the
ground-truth plan_runtime for a single zeroshot PostgreSQL plan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo))

from src.zeroshot.zeroshot_to_t3 import load_zeroshot_json, zeroshot_plan_to_t3
from src.zeroshot.training_zeroshot_tpch_holdout import load_benchmarked_queries_from_zeroshot

FILE = _repo / "zero-shot-data" / "runs" / "parsed_plans" / "tpc_h" / "workload_100k_s1_c8220.json"
PLAN_IDX = 2


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

    name = f"{json_path.stem}_{plan_idx}" if len(plans) > 1 else json_path.stem
    bq = bqs_by_name.get(name)
    plan_pipelines = bq.query_plan.pipelines if bq else None

    all_starts = [p["start"] for p in pipes_raw]
    all_stops  = [p["stop"]  for p in pipes_raw]
    analyze_plan_runtime_s = (max(all_stops) - min(all_starts)) / 1_000_000

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

    print(f"\n{'='*82}")
    print(f"  {json_path.name}  [plan index {plan_idx}]")
    print(f"{'='*82}")
    print("\n── JSON plan ──")
    print(json.dumps(zs_plan, indent=2))
    print()
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
        print(f"  P{i:<4}  {ops[:32]:<32}  {p_raw['start']:>11.0f}  {p_raw['stop']:>11.0f}  {span:>9.0f}  {raw:>10.6f}  {corrected:>13.6f}")

    print(sep)
    print(f"  {'SUM':<5}  {'':32}  {'':>11}  {'':>11}  {'':>9}  {raw_sum:>10.6f}  {plan_runtime_s:>13.6f}")
    print()
    print(f"  Gap BEFORE correction : {gap_s:.6f} s  ({gap_pct:.1f}%)")
    print(f"  Correction factor     : {correction:.6f}")
    print(f"  Pipelines with 0 span : {zero_pipes} / {len(raw_times)}"
          + ("  ← sub-ms nodes rounded to 0" if zero_pipes else ""))


if __name__ == "__main__":
    if not FILE.is_file():
        print(f"Error: file not found: {FILE}")
        sys.exit(1)

    print(f"\nLoading plan {PLAN_IDX} from {FILE.name} ...")
    bqs = load_benchmarked_queries_from_zeroshot([FILE], use_actual_card=True)
    bqs_by_name = {b.name: b for b in bqs}

    pipeline_gap(FILE, PLAN_IDX, bqs_by_name)
    print()
