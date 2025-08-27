# Cisco Manual Parser (Hybrid PDF → JSON)

A production-ready, layout-aware parser that converts Cisco-style error message manuals (PDF) into JSON using a **hybrid approach** (deterministic parsing + light fuzzy recovery).

## Output schema (now includes "Facility")
Each record uses these exact keys:
```json
{
  "Raw Error Text": "…",
  "Facility": "AAA",              // or "AAA-SUB" if a subfacility exists
  "Error Code": "ACCT_IOMEM_LOW",
  "Error Message": "…",
  "Explanation": "…",
  "Recommended Action": "…",
  "Severity": 3,
  "Page": 3
}
```

## Install
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

## Usage
```bash
# Array JSON (small/medium files)
python -m cisco_parser.parse_manual [input.pdf] --out [output/out.json] --validate

# NDJSON (recommended for large manuals)
python -m cisco_parser.parse_manual [input.pdf] --ndjson --out [output/out.json] --validate

# Chunk pages into shards (e.g., 200 pages per file) and show progress
python -m cisco_parser.parse_manual [input.pdf] --ndjson --out [output/out.ndjson] --chunk-pages 200 --progress
```

## Progress logging
Add `--progress` to log a line every `--progress-every` records (default 500):
```
INFO Progress: 500 records parsed (last page 42)
```

## Validation
`--validate` checks each record against a strict JSON Schema. Required keys: `"Raw Error Text"`, `"Facility"`, `"Error Code"`, `"Error Message"`, `"Severity"`, `"Page"`.

## Notes
- **Facility** is derived from the header `%FACILITY(-SUBFACILITY)?-SEVERITY-MNEMONIC : ...`
- Newline handling avoids word-smashing: `in\nthe` → `in the`; hyphenation `in-\nput` → `input`.
- Back-matter pages without `%...` entries are ignored automatically.
