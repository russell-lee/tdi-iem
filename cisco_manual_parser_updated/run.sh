#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run.sh /path/to/manual.pdf out.json [--csv-out out.csv] [parser args...]
#   ./run.sh --rebuild-venv /path/to/manual.pdf out.json [--csv-out out.csv] [parser args...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
REQ_HASH_FILE="$VENV_DIR/.requirements.sha256"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Optional: force a clean venv
if [[ "${1:-}" == "--rebuild-venv" ]]; then
  shift
  echo "Rebuilding virtual environment..."
  rm -rf "$VENV_DIR"
fi

# Create venv if missing
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment in $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/Scripts/activate"

# Make sure pip is reasonably current
python -m pip -q install --upgrade pip

# Compute requirements hash (so we only install when it changes)
hash_cmd=""
if command -v shasum >/dev/null 2>&1; then
  hash_cmd='shasum -a 256'
elif command -v sha256sum >/dev/null 2>&1; then
  hash_cmd='sha256sum'
fi

current_hash=""
if [[ -n "$hash_cmd" && -f "$REQ_FILE" ]]; then
  current_hash="$($hash_cmd "$REQ_FILE" | awk '{print $1}')"
fi
prev_hash=""
if [[ -f "$REQ_HASH_FILE" ]]; then
  prev_hash="$(cat "$REQ_HASH_FILE")"
fi

# Install deps only if requirements changed (or first run)
if [[ "$current_hash" != "$prev_hash" ]]; then
  echo "Installing/updating dependencies from $REQ_FILE ..."
  python -m pip install -r "$REQ_FILE" --upgrade --upgrade-strategy only-if-needed
  if [[ -n "$current_hash" ]]; then
    echo "$current_hash" > "$REQ_HASH_FILE"
  fi
else
  echo "Dependencies up to date; skipping pip install."
fi

# --- Parse required args ---
PDF_IN="${1:-}"
OUT_FILE="${2:-out.json}"
if [[ -z "$PDF_IN" ]]; then
  echo "Usage: ./run.sh /path/to/manual.pdf out.json [--csv-out out.csv] [parser args...]"
  exit 1
fi
# Shift off the two required args (if present)
[[ $# -ge 1 ]] && shift
[[ $# -ge 1 ]] && shift

# --- Optional CSV argument handling ---
# We pass through --csv-out if the user provides it. We also:
# - accept a shorthand '--csv <path>' and translate it to '--csv-out <path>'
# - accept env vars CSV_OUT / CSV_PATH / CSV when --csv-out not present
EXTRA_ARGS=("$@")
CSV_ARG=()

# Detect explicit --csv-out
HAS_CSV_OUT=0
for ((i=0; i<${#EXTRA_ARGS[@]}; i++)); do
  if [[ "${EXTRA_ARGS[i]}" == "--csv-out" ]]; then
    HAS_CSV_OUT=1
    break
  fi
done

# Translate '--csv <path>' to '--csv-out <path>'
if [[ $HAS_CSV_OUT -eq 0 ]]; then
  for ((i=0; i<${#EXTRA_ARGS[@]}; i++)); do
    if [[ "${EXTRA_ARGS[i]}" == "--csv" ]]; then
      if (( i+1 < ${#EXTRA_ARGS[@]} )); then
        CSV_OUT_VAL="${EXTRA_ARGS[i+1]}"
        # Remove '--csv' and its value
        EXTRA_ARGS=("${EXTRA_ARGS[@]:0:i}" "${EXTRA_ARGS[@]:i+2}")
        CSV_ARG=(--csv-out "$CSV_OUT_VAL")
      else
        echo "Error: --csv requires a path" >&2
        exit 2
      fi
      break
    fi
  done
fi

# If no explicit/translated CSV yet, fallback to env vars
if [[ ${#CSV_ARG[@]} -eq 0 && $HAS_CSV_OUT -eq 0 ]]; then
  if [[ -n "${CSV_OUT:-}" ]]; then
    CSV_ARG=(--csv-out "$CSV_OUT")
  elif [[ -n "${CSV_PATH:-}" ]]; then
    CSV_ARG=(--csv-out "$CSV_PATH")
  elif [[ -n "${CSV:-}" ]]; then
    CSV_ARG=(--csv-out "$CSV")
  fi
fi

# Ensure output directories exist (best effort), excluding stdout devices
mkdir -p "$(dirname "$OUT_FILE")" 2>/dev/null || true
if [[ ${#CSV_ARG[@]} -gt 0 ]]; then
  CSV_TARGET="${CSV_ARG[1]}"
  if [[ "$CSV_TARGET" != "-" && "$CSV_TARGET" != "/dev/stdout" && "$CSV_TARGET" != "/dev/stderr" ]]; then
    mkdir -p "$(dirname "$CSV_TARGET")" 2>/dev/null || true
  fi
fi

# (Optional) run tests before parsing
# pytest -q

# Run the parser (pass through any extra CLI flags)
python -m cisco_parser.parse_manual "$PDF_IN" --out "$OUT_FILE" "${CSV_ARG[@]}" "${EXTRA_ARGS[@]}"
echo "Done. Wrote: $OUT_FILE"
if [[ ${#CSV_ARG[@]} -gt 0 ]]; then
  echo "Also wrote CSV to: ${CSV_ARG[1]}"
fi
