import argparse
import json
from collections import Counter
from pathlib import Path

import jsonschema


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Validate output and compute simple metrics")
    p.add_argument("ndjson", help="NDJSON produced by cli.emit")
    p.add_argument("--schema", required=True, help="Schema JSON file")
    p.add_argument("--outdir", required=True, help="Directory for reports")
    args = p.parse_args(argv)

    records = [json.loads(line) for line in Path(args.ndjson).read_text(encoding="utf-8").splitlines() if line.strip()]
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)

    errors = []
    for idx, rec in enumerate(records):
        for err in validator.iter_errors(rec):
            errors.append(f"record {idx}: {err.message}")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "total": len(records),
        "field_completeness": sum(bool(v) for r in records for v in r.values()) / (len(records) * len(records[0]) if records else 1),
        "severity_distribution": Counter(r.get("Severity") for r in records),
        "errors": errors,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = [f"Total records: {metrics['total']}", f"Validation errors: {len(errors)}"]
    (outdir / "summary.md").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
