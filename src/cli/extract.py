import argparse
import json
from pathlib import Path

import pdfplumber


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Extract pages from a manual PDF")
    p.add_argument("pdf", help="Input PDF")
    p.add_argument("--out", required=True, help="Output JSON file")
    args = p.parse_args(argv)

    pages = []
    with pdfplumber.open(args.pdf) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": idx, "text": text})
    Path(args.out).write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
