import argparse
import json
from pathlib import Path

from parser.manual import parse_lines


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Parse extracted pages into records")
    p.add_argument("pages", help="JSON produced by cli.extract")
    p.add_argument("--rules", help="Rules YAML", default="rules/base.yml")
    p.add_argument("--out", required=True, help="Output JSON file")
    args = p.parse_args(argv)

    pages = json.loads(Path(args.pages).read_text(encoding="utf-8"))
    records = []
    for page in pages:
        lines = page["text"].splitlines()
        for rec in parse_lines(lines):
            rec["Page"] = page["page"]
            records.append(rec)
    Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
