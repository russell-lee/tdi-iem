#!/usr/bin/env bash
set -euo pipefail

PDF=${1:-data/raw/manual.pdf}
OUT=${2:-data/interim/pages.json}

python -m cli.extract "$PDF" --out "$OUT"
