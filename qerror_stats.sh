#!/usr/bin/env bash
# Usage: ./qerror_stats.sh [file] [start_line] [end_line]
# Default: job_light_zero_t3_results.txt lines 119-168

FILE="${1:-job_light_zero_t3_results.txt}"
START="${2:-119}"
END="${3:-168}"

sed -n "${START},${END}p" "$FILE" | awk -F'q_error=' '
  $2 != "" { gsub(/[^0-9.]/, "", $2); if ($2 != "") print $2 }
' | sort -n | awk '
  { a[NR]=$1; sum+=$1 }
  END {
    n = NR
    if (n == 0) { print "no values"; exit }
    p50 = (n % 2) ? a[(n+1)/2] : (a[n/2]+a[n/2+1])/2
    p70 = a[int(0.7*n+0.5)]
    p90 = a[int(0.9*n+0.5)]
    printf "avg=%.4f p50=%.4f p70=%.4f p90=%.4f min=%.4f max=%.4f (n=%d)\n",
           sum/n, p50, p70, p90, a[1], a[n], n
  }
'
