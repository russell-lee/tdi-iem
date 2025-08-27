import re
import re

from test_json_output import load_data

HEADER_RE = re.compile(r"%[A-Z]+-\d-")


def test_no_field_contamination():
    data = load_data()
    for obj in data:
        for field in ("Explanation", "Recommended Action"):
            text = obj.get(field) or ""
            assert "Explanation:" not in text
            assert "Recommended Action:" not in text
            assert not HEADER_RE.search(text)

