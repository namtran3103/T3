#!/usr/bin/env bash
# Run all zeroshot holdouts in all four configurations (per-pipeline + query-level).
# Delegates to run_all_holdouts_pipeline.sh and run_all_holdouts_ql.sh.
# Run from the T3 project root (directory containing src/).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Per-pipeline runs ==="
bash run_all_holdouts_pipeline.sh

echo "=== Query-level runs ==="
bash run_all_holdouts_ql.sh

echo "Done."
