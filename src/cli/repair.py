import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Apply rule-based repairs to records")
    p.add_argument("parsed", help="JSON produced by cli.parse")
    p.add_argument("--rules", help="Repairs YAML", default="rules/repairs.yml")
    p.add_argument("--out", required=True, help="Output JSON file")
    args = p.parse_args(argv)

    data = json.loads(Path(args.parsed).read_text(encoding="utf-8"))
    # Placeholder: no actual repairs yet.
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
