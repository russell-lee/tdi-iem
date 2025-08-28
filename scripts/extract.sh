#!/usr/bin/env bash
set -euo pipefail

PDF=${1:-data/raw/manual.pdf}
OUT=${2:-data/interim/pages.json}

# Ensure the project sources are discoverable by the Python interpreter
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/../src:${PYTHONPATH:-}"

python -m cli.extract "$PDF" --out "$OUT"
