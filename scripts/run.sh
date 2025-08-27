#!/usr/bin/env bash
set -euo pipefail

PDF=${1:-data/raw/manual.pdf}

python -m cli.extract "$PDF" --out data/interim/pages.json
python -m cli.parse data/interim/pages.json --out data/interim/parsed.json
python -m cli.repair data/interim/parsed.json --out data/processed/out.json
python -m cli.emit data/processed/out.json --ndjson --out data/processed/out.ndjson
