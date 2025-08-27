import json
import sys
from pathlib import Path

# Ensure package root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

DATA_FILE = ROOT / "out_small.json"


def load_data():
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def test_json_structure_and_types():
    data = load_data()
    assert isinstance(data, list) and data
    required = {
        "Raw Error Text",
        "Facility",
        "Error Code",
        "Error Message",
        "Explanation",
        "Recommended Action",
        "Severity",
        "Page",
    }
    for obj in data:
        assert required <= obj.keys()
        assert isinstance(obj["Severity"], int)
        assert 0 <= obj["Severity"] <= 7
        assert isinstance(obj["Page"], int) and obj["Page"] > 0


def test_raw_text_matches_fields():
    data = load_data()
    for obj in data:
        header = f"%{obj['Facility']}-{obj['Severity']}-{obj['Error Code']}"
        assert obj["Raw Error Text"].startswith(header)


def test_first_entry_sample_values():
    data = load_data()
    first = data[0]
    assert first["Facility"] == "AAA"
    assert first["Severity"] == 2
    assert first["Error Code"] == "AAAMULTILINKERROR"
    assert first["Explanation"].startswith("AAA internal error")
