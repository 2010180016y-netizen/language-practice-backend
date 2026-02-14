#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
IN_FILE=${1:?Usage: restore.sh <backup.dump>}
pg_restore -d "$DATABASE_URL" --clean --if-exists "$IN_FILE"
echo "Restore completed from: $IN_FILE"
