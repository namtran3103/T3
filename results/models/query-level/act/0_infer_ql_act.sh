#!/usr/bin/env bash
# Run query-level inference with actual cardinalities for all models in
# the same directory as this script and append results to 0_results.txt.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

MODEL_DIR="$SCRIPT_DIR"
OUTPUT="$MODEL_DIR/0_results.txt"

# Clear previous results
> "$OUTPUT"

cd "$REPO_ROOT"

for model_file in "$MODEL_DIR"/*.txt; do
    name="$(basename "$model_file" .txt)"
    # Skip the aggregated results file itself
    [[ "$name" == "0_results" ]] && continue

    echo "==> Inferring: $name"
    python -m src.zeroshot.inference_zeroshot_holdout \
        --holdout "$name" \
        --model "$model_file" \
        --query-level \
        --out "$OUTPUT"
done

echo ""
echo "Done. Results written to $OUTPUT"
