#!/usr/bin/env bash
# Run per-pipeline zeroshot holdouts:
#   1. actual cardinality
#   2. estimated cardinality
# Run from the T3 project root (directory containing src/).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== run_all_holdouts (actual cardinality) ==="
python -m src.zeroshot.run_all_holdouts

echo "=== run_all_holdouts (--use-estimated-card) ==="
python -m src.zeroshot.run_all_holdouts --use-estimated-card

echo "Done."
