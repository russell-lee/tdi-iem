#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cisco Manual Parser
- Parses Cisco IOS/IOS-XE System Message Guide PDFs into JSON (array or NDJSON).
- Adds optional parallel CSV output via --csv-out with columns:
  1) Facility-Severity-Mnemonic
  2) Message            (maps to "Error Message")
  3) Explanation
  4) Recommended Action

Key features:
- Robust header detection across page breaks with a small pending-header buffer.
- Avoids “label in header” contamination when a joined header’s message starts
  with Explanation / Recommended Action (keeps message empty, treats next line as label).
- Header-message continuation heuristic to capture short, wrapped message lines that
  follow immediately after header and are unlabeled.
- Post-parse fixers to move mislabeled text out of "Error Message" and to truncate
  fields at the next detected header.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from typing import Dict, Iterable, Iterator, List, Optional

# -------------------------
# Regexes and label helpers
# -------------------------

# Lines that START with '%' only
HEADER_START_RE = re.compile(r"^\s*%")

# Full entry header: %FAC[-SUB]-SEV-MNEM : message...
ENTRY_HEADER_RE = re.compile(
    r"""
    ^\s*%
    (?P<facility>[A-Z0-9_]+)
    (?:-(?P<subfacility>[A-Z0-9_]+))?
    -
    (?P<severity>[0-7])
    -
    (?P<mnemonic>[A-Z0-9_]+)
    \s*:\s*
    (?P<message>.*)
    $
    """,
    re.X,
)

# Header prefix ONLY (up to colon; no message captured)
ENTRY_HEADER_PREFIX_RE = re.compile(
    r"""
    ^\s*%
    (?P<facility>[A-Z0-9_]+)
    (?:-(?P<subfacility>[A-Z0-9_]+))?
    -
    (?P<severity>[0-7])
    -
    (?P<mnemonic>[A-Z0-9_]+)
    \s*:\s*$
    """,
    re.X,
)

LABEL_START_RE = re.compile(
    r"^\s*(Explanation|Recommended\s*Action)\b\s*:?", re.I
)

LABELS_CANON = ["Explanation", "Recommended Action"]


def fuzzy_label_match(line: str, labels: List[str]) -> Optional[str]:
    t = line.strip().lower().replace("  ", " ")
    for lab in labels:
        base = lab.lower().replace("  ", " ")
        if t.startswith(base) or t.startswith(base + ":"):
            return lab
    return None


# -------------------------
# CLI / logging
# -------------------------

def setup_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parse Cisco system message PDF to JSON/NDJSON (and optional CSV).")
    p.add_argument("pdf", help="Path to PDF manual.")
    p.add_argument("--out", type=str, default=None, help="Output path (JSON array or NDJSON if --ndjson). If omitted, prints to stdout.")
    p.add_argument("--ndjson", action="store_true", help="Emit NDJSON (one JSON object per line).")
    p.add_argument("--limit", type=int, default=0, help="Maximum number of records to emit (0 = no limit).")
    p.add_argument("--log", type=str, default="INFO", help="Log level: DEBUG, INFO, WARNING, ERROR.")
    p.add_argument("--chunk-pages", type=int, default=0, help="For NDJSON, process pages in chunks (e.g., 200). 0 = all pages.")
    p.add_argument("--progress", action="store_true", help="Log periodic progress.")
    p.add_argument("--progress-every", type=int, default=1000, help="Progress log frequency (records).")
    p.add_argument("--validate", action="store_true", help="Validate JSON objects (basic checks).")
    p.add_argument("--csv-out", type=str, default=None, help="Optional CSV output path.")
    return p.parse_args(argv)


# -------------------------
# PDF utilities
# -------------------------

def is_all_caps_heading(line: str) -> bool:
    t = line.strip()
    if len(t) < 3 or len(t.split()) > 8:
        return False
    # A crude filter for section headings in manuals
    if t.isupper() and t.replace("-", "").replace("_", "").replace(" ", "").isalpha():
        return True
    return False


def strip_headers_footers(page) -> str:
    """
    Remove common header/footer bands; fall back gracefully if cropping not supported.
    """
    try:
        top_cut = page.height * 0.07
        bottom_cut = page.height * 0.93
        # Prefer crop (no context manager); fallback to within_bbox; fallback to full page
        try:
            clipped = page.crop((0, top_cut, page.width, bottom_cut))
        except Exception:
            try:
                clipped = page.within_bbox((0, top_cut, page.width, bottom_cut))
            except Exception:
                clipped = None
        if clipped is not None:
            text = clipped.extract_text(x_tolerance=1.5, y_tolerance=3.0) or ""
        else:
            text = page.extract_text() or ""
    except Exception:
        text = page.extract_text() or ""
    return text


# -------------------------
# CSV helpers
# -------------------------

def make_fsn(obj: Dict[str, object]) -> str:
    fac = (obj.get("Facility") or "").replace("%", "").strip()
    sev = obj.get("Severity")
    sev_s = "" if sev is None else str(sev)
    mnem = (obj.get("Error Code") or "").replace("%", "").strip()
    parts = [p for p in (fac, sev_s, mnem) if p != ""]
    return "-".join(parts)


def csv_row_for(obj: Dict[str, object]) -> List[str]:
    return [
        make_fsn(obj),
        obj.get("Error Message") or "",
        obj.get("Explanation") or "",
        obj.get("Recommended Action") or "",
    ]


# -------------------------
# Validation
# -------------------------

def validate_item(obj: Dict[str, object]) -> None:
    req_keys = [
        "Raw Error Text",
        "Facility",
        "Error Code",
        "Error Message",
        "Explanation",
        "Recommended Action",
        "Severity",
        "Page",
    ]
    for k in req_keys:
        if k not in obj:
            raise ValueError(f"Missing key: {k}")

    if obj["Raw Error Text"] is not None and not isinstance(obj["Raw Error Text"], str):
        raise TypeError("Raw Error Text must be str or None")

    if obj["Facility"] is not None and not isinstance(obj["Facility"], str):
        raise TypeError("Facility must be str or None")

    if obj["Error Code"] is not None and not isinstance(obj["Error Code"], str):
        raise TypeError("Error Code must be str or None")

    if obj["Error Message"] is not None and not isinstance(obj["Error Message"], str):
        raise TypeError("Error Message must be str or None")

    for k in ("Explanation", "Recommended Action"):
        if obj[k] is not None and not isinstance(obj[k], str):
            raise TypeError(f"{k} must be str or None")

    if obj["Severity"] is not None:
        if not isinstance(obj["Severity"], int) or not (0 <= obj["Severity"] <= 7):
            raise TypeError("Severity must be int in [0..7] or None")

    if not isinstance(obj["Page"], int) or obj["Page"] <= 0:
        raise TypeError("Page must be a positive int")


def page_ranges(total_pages: int, chunk: int) -> Iterable[tuple[int, int]]:
    if chunk <= 0:
        return [(1, total_pages)]
    out = []
    start = 1
    while start <= total_pages:
        end = min(total_pages, start + chunk - 1)
        out.append((start, end))
        start = end + 1
    return out


# -------------------------
# Post-parse fixers
# -------------------------

def _strip_at_new_header(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    lines = str(text).splitlines()
    out = []
    for ln in lines:
        if ENTRY_HEADER_RE.match(ln.strip()):
            break
        out.append(ln)
    cleaned = "\n".join(out).strip()
    return cleaned if cleaned else None


_label_msg_re = re.compile(r"^(Explanation|Recommended\s*Action)\s*:?\s*(.*)$", re.I)


def fix_record(obj: Dict[str, object]) -> Dict[str, object]:
    """
    Post-parse repairs:
      - If Error Message begins with 'Explanation' or 'Recommended Action', move text into that field.
      - Truncate Explanation/Recommended Action at first new header.
      - If Error Message is empty and Raw Error Text's message shows a label, strip it from Raw Error Text.
    """
    # Move mislabeled content out of Error Message
    msg = obj.get("Error Message")
    expl = obj.get("Explanation")
    rec = obj.get("Recommended Action")

    if isinstance(msg, str):
        m = _label_msg_re.match(msg.strip())
        if m:
            label, rest = m.group(1), m.group(2)
            if label.lower().startswith("explanation") and not expl:
                obj["Explanation"] = rest if rest else None
                obj["Error Message"] = None
            elif label.lower().startswith("recommended action") and not rec:
                obj["Recommended Action"] = rest if rest else None
                obj["Error Message"] = None

    # Truncate fields at new header
    obj["Explanation"] = _strip_at_new_header(obj.get("Explanation"))
    obj["Recommended Action"] = _strip_at_new_header(obj.get("Recommended Action"))

    # Clean Raw Error Text if it accidentally contains a label as message while Error Message is empty
    raw = obj.get("Raw Error Text")
    if (obj.get("Error Message") in (None, "")) and isinstance(raw, str):
        mraw = ENTRY_HEADER_RE.match(raw.strip())
        if mraw:
            msg_raw = (mraw.group("message") or "").strip()
            if LABEL_START_RE.match(msg_raw):
                fac = mraw.group("facility")
                subfac = mraw.group("subfacility")
                sev = mraw.group("severity")
                mnem = mraw.group("mnemonic")
                subpart = f"-{subfac}" if subfac else ""
                obj["Raw Error Text"] = f"%{fac}{subpart}-{sev}-{mnem} :"

    return obj


# -------------------------
# Header continuation heuristic
# -------------------------

CONT_MAX_LINES = 2  # don't over-absorb explanatory prose


def should_continue_header(msg_so_far: str, next_line: str) -> bool:
    """
    Consider 'next_line' a continuation of the header's Error Message if:
      - It's not a new header or a field label, AND
      - The current message ends with comma/hyphen/slash/colon, OR
      - The current message lacks sentence punctuation and next line doesn't look like a prose opener.
    """
    if not msg_so_far:
        return False
    nl = (next_line or "").lstrip()
    if HEADER_START_RE.match(nl) or LABEL_START_RE.match(nl) or is_all_caps_heading(nl):
        return False

    ms = msg_so_far.rstrip()
    if ms.endswith((",", "-", "/", ":")):
        return True

    if not re.search(r"[.?!\]\)]\s*$", ms):
        if not re.match(r"^(This|The|Either|If|When|In case|For|To)\b", nl):
            return True
    return False


# -------------------------
# Core streaming parser
# -------------------------

def iter_entries_streaming(pdf, start_page: int, end_page: Optional[int] = None) -> Iterator[Dict[str, object]]:
    """
    Stream entries across page boundaries with:
      - pending-header buffer (only '%' lines),
      - label-in-header protection on join,
      - message continuation heuristic for unlabeled lines immediately after header.
    """
    if end_page is None:
        end_page = len(pdf.pages)

    current: Optional[Dict[str, object]] = None
    current_label: Optional[str] = None
    pending_header_line: Optional[str] = None
    pending_header_page: Optional[int] = None
    header_cont_count: int = 0

    def finalize():
        nonlocal current
        if current:
            for k in ("Explanation", "Recommended Action"):
                v = current.get(k)
                current[k] = v.strip() if v else None
            yield {
                "Raw Error Text": current.get("Raw Error Text"),
                "Facility": current.get("Facility"),
                "Error Code": current.get("Error Code"),
                "Error Message": current.get("Error Message"),
                "Explanation": current.get("Explanation"),
                "Recommended Action": current.get("Recommended Action"),
                "Severity": current.get("Severity"),
                "Page": current.get("Page"),
            }
            current = None

    def flush_pending_as_body():
        nonlocal pending_header_line, pending_header_page
        # We drop pending raw '%' lines by default to avoid contaminating bodies.
        pending_header_line = None
        pending_header_page = None

    for page_num in range(start_page, end_page + 1):
        page = pdf.pages[page_num - 1]
        page_text = strip_headers_footers(page)
        if not page_text.strip():
            continue

        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line or is_all_caps_heading(line):
                continue

            # If we have a pending '%' line, attempt to join with this line
            if pending_header_line is not None:
                candidate = (pending_header_line + " " + line).strip()
                m_join = ENTRY_HEADER_RE.match(candidate)
                if m_join:
                    # Avoid 'label in header' if the joined message begins with a label.
                    joined_msg = m_join.group("message").strip() if m_join.group("message") else ""
                    if LABEL_START_RE.match(joined_msg):
                        # Build entry from prefix only (pending line), then process this line normally
                        m_pref = ENTRY_HEADER_PREFIX_RE.match(pending_header_line.strip())
                        if m_pref:
                            yield from finalize()
                            facility = m_pref.group("facility")
                            subfacility = m_pref.group("subfacility")
                            fac_full = facility if not subfacility else f"{facility}-{subfacility}"
                            severity = m_pref.group("severity")
                            try:
                                sev_int = int(severity) if severity is not None else None
                            except Exception:
                                sev_int = None
                            current = {
                                "Raw Error Text": pending_header_line.strip(),
                                "Facility": fac_full,
                                "Error Code": m_pref.group("mnemonic"),
                                "Error Message": None,
                                "Explanation": "",
                                "Recommended Action": "",
                                "Severity": sev_int,
                                "Page": pending_header_page,
                            }
                            current_label = None
                            header_cont_count = 0
                            pending_header_line = None
                            pending_header_page = None
                            # fall through to process current 'line' as label/content
                        else:
                            flush_pending_as_body()
                    else:
                        # Normal joined header path
                        yield from finalize()
                        facility = m_join.group("facility")
                        subfacility = m_join.group("subfacility")
                        fac_full = facility if not subfacility else f"{facility}-{subfacility}"
                        severity = m_join.group("severity")
                        try:
                            sev_int = int(severity) if severity is not None else None
                        except Exception:
                            sev_int = None
                        current = {
                            "Raw Error Text": candidate,
                            "Facility": fac_full,
                            "Error Code": m_join.group("mnemonic"),
                            "Error Message": m_join.group("message"),
                            "Explanation": "",
                            "Recommended Action": "",
                            "Severity": sev_int,
                            "Page": pending_header_page,  # where the header started
                        }
                        current_label = None
                        header_cont_count = 0
                        pending_header_line = None
                        pending_header_page = None
                        continue
                else:
                    # Not a full header → drop pending to avoid pollution
                    flush_pending_as_body()

            # 2) Full header on this line?
            m = ENTRY_HEADER_RE.match(line)
            if m:
                yield from finalize()
                facility = m.group("facility")
                subfacility = m.group("subfacility")
                fac_full = facility if not subfacility else f"{facility}-{subfacility}"
                severity = m.group("severity")
                try:
                    sev_int = int(severity) if severity is not None else None
                except Exception:
                    sev_int = None
                current = {
                    "Raw Error Text": line,
                    "Facility": fac_full,
                    "Error Code": m.group("mnemonic"),
                    "Error Message": m.group("message"),
                    "Explanation": "",
                    "Recommended Action": "",
                    "Severity": sev_int,
                    "Page": page_num,
                }
                current_label = None
                header_cont_count = 0
                continue

            # 3) Potential header prefix? hold for next line/page
            if HEADER_START_RE.match(line):
                pending_header_line = line
                pending_header_page = page_num
                continue

            # 4) Labeled sections (exact)
            labeled = False
            for canon in ("Explanation", "Recommended Action"):
                if re.match(rf"^{re.escape(canon)}\b\s*:?", line, flags=re.I):
                    rest = re.sub(rf"^{re.escape(canon)}\s*:?\s*", "", line, flags=re.I)
                    current_label = canon
                    if current is not None and rest:
                        key = "Explanation" if canon == "Explanation" else "Recommended Action"
                        body = current.get(key, "")
                        current[key] = (body + ("\n" if body else "") + rest)
                    labeled = True
                    break
            if labeled:
                continue

            # 5) Fuzzy label recovery
            flabel = fuzzy_label_match(line, LABELS_CANON)
            if flabel:
                rest = re.sub(r"^.*?:\s*", "", line) if ":" in line else ""
                current_label = flabel
                if current is not None and rest:
                    key = "Explanation" if flabel == "Explanation" else "Recommended Action"
                    body = current.get(key, "")
                    current[key] = (body + ("\n" if body else "") + rest)
                continue

            # 6) Plain content: either append to active label OR continue header message
            if current is not None:
                if current_label in ("Explanation", "Recommended Action"):
                    key = "Explanation" if current_label == "Explanation" else "Recommended Action"
                    body = current.get(key, "")
                    current[key] = (body + ("\n" if body else "") + line)
                else:
                    # Unlabeled, immediately after header: continue message if heuristic allows
                    emsg = current.get("Error Message") or ""
                    if header_cont_count < CONT_MAX_LINES and should_continue_header(emsg, line):
                        sep = " " if (emsg and not emsg.endswith(("-", "/", ":"))) else ""
                        current["Error Message"] = emsg + sep + line
                        header_cont_count += 1
                    else:
                        # Otherwise ignore, or route to Explanation if you prefer
                        pass

    # flush any dangling pending
    pending_header_line = None
    pending_header_page = None

    # finalize last entry
    yield from finalize()


def process_pages_range(pdf, start_page: int, end_page: int) -> Iterator[Dict[str, object]]:
    """Yield output dicts for pages in [start_page, end_page], preserving cross-page entries."""
    for obj in iter_entries_streaming(pdf, start_page, end_page):
        yield obj


# -------------------------
# Main
# -------------------------

def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.log)

    total = 0
    csv_file = open(args.csv_out, "w", newline="", encoding="utf-8") if args.csv_out else None
    csv_writer = csv.writer(csv_file) if csv_file else None
    if csv_writer:
        csv_writer.writerow(["Facility-Severity-Mnemonic", "Message", "Explanation", "Recommended Action"])

    from contextlib import nullcontext
    import pdfplumber

    try:
        if args.ndjson:
            with pdfplumber.open(args.pdf) as pdf:
                total_pages = len(pdf.pages)
                # stdout vs file
                if not args.out:
                    sink_cm = nullcontext(sys.stdout)
                    with sink_cm as sink:
                        for (start, end) in page_ranges(total_pages, args.chunk_pages):
                            for obj in process_pages_range(pdf, start, end):
                                obj = fix_record(obj)
                                if args.validate:
                                    try:
                                        validate_item(obj)
                                    except Exception as ve:
                                        logging.warning("Validation failed p%s: %s", obj.get("Page"), ve)
                                json.dump(obj, sink, ensure_ascii=False)
                                sink.write("\n")
                                if csv_writer:
                                    csv_writer.writerow(csv_row_for(obj))
                                total += 1
                                if args.progress and (total % args.progress_every == 0):
                                    logging.info("Progress: %d records parsed (last page %s)", total, obj.get("Page"))
                                if args.limit and total >= args.limit:
                                    break
                            if args.limit and total >= args.limit:
                                break
                else:
                    base = args.out
                    with open(base, "w", encoding="utf-8") as sink:
                        for (start, end) in page_ranges(len(pdfplumber.open(args.pdf).pages), args.chunk_pages or 0):
                            with pdfplumber.open(args.pdf) as pdf2:
                                for obj in process_pages_range(pdf2, start, end):
                                    obj = fix_record(obj)
                                    if args.validate:
                                        try:
                                            validate_item(obj)
                                        except Exception as ve:
                                            logging.warning("Validation failed p%s: %s", obj.get("Page"), ve)
                                    json.dump(obj, sink, ensure_ascii=False)
                                    sink.write("\n")
                                    if csv_writer:
                                        csv_writer.writerow(csv_row_for(obj))
                                    total += 1
                                    if args.progress and (total % args.progress_every == 0):
                                        logging.info("Progress: %d records parsed (last page %s)", total, obj.get("Page"))
                                    if args.limit and total >= args.limit:
                                        break
                            if args.limit and total >= args.limit:
                                break
        else:
            # JSON array mode
            arr: List[Dict[str, object]] = []
            with pdfplumber.open(args.pdf) as pdf:
                total_pages = len(pdf.pages)
                for obj in process_pages_range(pdf, 1, total_pages):
                    obj = fix_record(obj)
                    if args.validate:
                        try:
                            validate_item(obj)
                        except Exception as ve:
                            logging.warning("Validation failed p%s: %s", obj.get("Page"), ve)
                    arr.append(obj)
                    if csv_writer:
                        csv_writer.writerow(csv_row_for(obj))
                    total += 1
                    if args.progress and (total % args.progress_every == 0):
                        logging.info("Progress: %d records parsed (last page %s)", total, obj.get("Page"))
                    if args.limit and total >= args.limit:
                        break

            if args.out:
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(arr, f, ensure_ascii=False, indent=2)
            else:
                json.dump(arr, sys.stdout, ensure_ascii=False, indent=2)

        logging.info("Parsed %d entries.", total)
        return 0
    finally:
        if csv_file:
            csv_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
