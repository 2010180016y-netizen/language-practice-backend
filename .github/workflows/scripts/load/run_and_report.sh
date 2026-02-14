#!/usr/bin/env bash
set -euo pipefail

HOST=${1:-http://localhost:8000}
OUT=${2:-load_test_report.txt}

locust -f scripts/load/locustfile.py --host "$HOST" --headless -u 50 -r 10 -t 60s --only-summary | tee "$OUT"

echo "Load test report saved to $OUT"
