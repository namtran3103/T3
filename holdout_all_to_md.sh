#!/usr/bin/env bash
# Generate markdown reports for all holdout result files.
# Run from the T3 project root (directory containing holdout_to_md.py).
# Creates: holdout_results.md, holdout_augmented_results.md, holdout_fewshot_results.md,
#          holdout_fewshot_100_results.md, etc., plus corresponding _p50_bars.png files.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Generating holdout markdown reports..."
python holdout_to_md.py
echo "  -> holdout_results.md"

python holdout_to_md.py --input holdout.txt --start-line 53 --end-line 99 --output holdout_results_new.md --jh holdout_jh.txt --jh-start-line 17 --jh-end-line 38 --jh2 holdout_jh.txt --jh2-start-line 51 --jh2-end-line 72 --jh2-title "all jh (fixed)" --extra-start-line 112 --extra-end-line 132 --extra-title "full run with fix" --extra2-start-line 143 --extra2-end-line 164 --extra2-title "updated nl feature"
echo "  -> holdout_results_new.md"

python holdout_to_md.py --input holdout_augmented.txt
echo "  -> holdout_augmented_results.md"

for f in holdout_fewshot.txt holdout_fewshot_*.txt; do
  if [[ -f "$f" ]]; then
    python holdout_to_md.py --input "$f"
    echo "  -> ${f%.txt}_results.md"
  fi
done

echo "Done."
