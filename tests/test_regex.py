import re
import sys
from pathlib import Path

# ensure src/ on path for import
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from parser.manual import ENTRY_HEADER_RE

def test_header_regex_basic():
    m = ENTRY_HEADER_RE.match("%AAA-3-ACCT_IOMEM_LOW : something happened")
    assert m
    assert m.group("mnemonic") == "ACCT_IOMEM_LOW"
    assert m.group("severity") == "3"
    assert m.group("message") == "something happened"
