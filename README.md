# Error Manual Parser

This repository provides a reproducible pipeline for converting vendor error
message manuals into structured JSON/NDJSON. The project is organised into
separate stages and configuration driven rules.

## Layout

```
src/        - parser logic and CLI entry points
rules/      - YAML configuration for regexes and repairs
data/       - raw, interim and processed artifacts
eval/       - schemas and evaluation reports
tests/      - unit tests and golden outputs
scripts/    - helpers and `run.sh`
```

## Pipeline

```
python -m cli.extract data/raw/manual.pdf --out data/interim/pages.json
python -m cli.parse   data/interim/pages.json --rules rules/base.yml --out data/interim/parsed.json
python -m cli.repair  data/interim/parsed.json --rules rules/repairs.yml --out data/processed/out.json
python -m cli.emit    data/processed/out.json --ndjson --out data/processed/out.ndjson
python -m cli.eval    data/processed/out.ndjson --schema eval/schema.json --outdir eval
```

A `Makefile` exposes common targets (`make build`, `make test`, etc.) and the
`scripts/run.sh` wrapper runs the full pipeline for convenience.
