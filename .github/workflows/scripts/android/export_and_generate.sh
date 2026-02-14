#!/usr/bin/env bash
set -euo pipefail

python scripts/export_openapi.py
python scripts/android/generate_retrofit_from_openapi.py

echo "Done: openapi.json + android Retrofit models generated"
