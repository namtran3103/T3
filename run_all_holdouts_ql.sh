#!/usr/bin/env bash
# Run query-level zeroshot holdouts:
#   1. actual cardinality
#   2. estimated cardinality
# Run from the T3 project root (directory containing src/).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== run_all_holdouts --query-level (actual cardinality) ==="
python -m src.zeroshot.run_all_holdouts --query-level

echo "=== run_all_holdouts --query-level (--use-estimated-card) ==="
python -m src.zeroshot.run_all_holdouts --query-level --use-estimated-card

echo "Done."
