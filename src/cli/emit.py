import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Emit final JSON or NDJSON output")
    p.add_argument("records", help="JSON produced by cli.repair")
    p.add_argument("--ndjson", action="store_true", help="Write NDJSON instead of array")
    p.add_argument("--out", required=True, help="Output file path")
    args = p.parse_args(argv)

    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    out_path = Path(args.out)
    if args.ndjson:
        with out_path.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
