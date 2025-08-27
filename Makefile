.PHONY: venv extract parse repair emit build eval test fmt

venv:
	python -m venv .venv

extract:
	python -m cli.extract data/raw/manual.pdf --out data/interim/pages.json

parse:
	python -m cli.parse data/interim/pages.json --out data/interim/parsed.json

repair:
	python -m cli.repair data/interim/parsed.json --out data/processed/out.json

emit:
	python -m cli.emit data/processed/out.json --ndjson --out data/processed/out.ndjson

build: extract parse repair emit

eval:
	python -m cli.eval data/processed/out.ndjson --schema eval/schema.json --outdir eval

test:
	pytest

fmt:
	black src tests
