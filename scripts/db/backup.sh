#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
OUT_FILE=${1:-backup_$(date +%Y%m%d_%H%M%S).dump}
pg_dump "$DATABASE_URL" -Fc -f "$OUT_FILE"
echo "Backup created: $OUT_FILE"
