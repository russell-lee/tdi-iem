import re
import sys
from pathlib import Path

# ensure package root on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from cisco_parser.parse_manual import ENTRY_HEADER_RE

def test_header_regex_basic():
    m = ENTRY_HEADER_RE.match("%AAA-3-ACCT_IOMEM_LOW : something happened")
    assert m
    assert m.group("mnemonic") == "ACCT_IOMEM_LOW"
    assert m.group("severity") == "3"
    assert m.group("message") == "something happened"
