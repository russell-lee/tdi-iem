#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parsing utilities for Cisco-style error manuals.

This module exposes regular expressions and a small helper for parsing
manual text into structured records. Heavy PDF handling and CLI logic
from the original project have been stripped out to keep the module
focused on pure parsing logic; I/O is handled in cli modules.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional

import yaml

SRC_ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = SRC_ROOT / "rules" / "base.yml"
with RULES_FILE.open("r", encoding="utf-8") as fh:
    _rules = yaml.safe_load(fh)

HEADER_START_RE = re.compile(_rules["header_start"])
ENTRY_HEADER_RE = re.compile(_rules["entry_header"], re.X)
ENTRY_HEADER_PREFIX_RE = re.compile(_rules["entry_header_prefix"], re.X)
LABELS_CANON = list(_rules["label_variants"].keys())
label_pattern = r"|".join(re.escape(lab) for lab in LABELS_CANON)
LABEL_START_RE = re.compile(rf"^\s*(?:{label_pattern})\b\s*:?", re.I)


def parse_lines(lines: Iterable[str]) -> Iterator[Dict[str, Optional[str]]]:
    """Parse a sequence of lines into error records.

    This very small parser is deterministic and intended mainly for tests.
    It only recognises headers and simple labeled fields.
    """
    current: Optional[Dict[str, Optional[str]]] = None
    for ln in lines:
        m = ENTRY_HEADER_RE.match(ln.strip())
        if m:
            if current:
                yield current
            current = {
                "Raw Error Text": ln.strip(),
                "Facility": m.group("facility"),
                "Error Code": m.group("mnemonic"),
                "Severity": int(m.group("severity")),
                "Error Message": m.group("message").strip() if m.group("message") else "",
                "Explanation": "",
                "Recommended Action": "",
            }
        elif current and LABEL_START_RE.match(ln):
            lab = LABEL_START_RE.match(ln).group(0).rstrip(":").strip()
            text = ln.split(":", 1)[1].strip() if ":" in ln else ""
            current[lab] = text
        elif current:
            current["Error Message"] = (
                (current.get("Error Message") or "") + " " + ln.strip()
            ).strip()
    if current:
        yield current


__all__ = [
    "HEADER_START_RE",
    "ENTRY_HEADER_RE",
    "ENTRY_HEADER_PREFIX_RE",
    "LABEL_START_RE",
    "LABELS_CANON",
    "parse_lines",
]
