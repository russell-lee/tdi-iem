import json
import re
import sys
from collections import Counter
from pathlib import Path


# Ensure src/ on path and locate golden data
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

DATA_FILE = Path(__file__).resolve().parent / "golden" / "out_small.json"


def load_data():
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def summarize_data() -> str:
    """Return a human-readable summary of the JSON dataset."""
    data = load_data()

    facilities = Counter(obj["Facility"] for obj in data)
    severity_counts = Counter(obj["Severity"] for obj in data)

    key_tuples = [(obj["Facility"], obj["Error Code"], obj["Severity"]) for obj in data]
    duplicate_count = len(data) - len(set(key_tuples))

    null_field_count = sum(
        1
        for obj in data
        for val in obj.values()
        if val is None or (isinstance(val, str) and not val.strip())
    )

    top_facilities = ", ".join(f"{fac}({cnt})" for fac, cnt in facilities.most_common(5))
    top_severities = ", ".join(f"{sev}({cnt})" for sev, cnt in severity_counts.most_common())

    lines = [
        f"Total entries: {len(data)}",
        f"Facilities: {len(facilities)} unique",
        "Severity counts: "
        + ", ".join(f"{sev}:{count}" for sev, count in sorted(severity_counts.items())),
        f"Duplicate entries: {duplicate_count}",
        f"Null/empty fields: {null_field_count}",
        f"Top facilities: {top_facilities}",
        f"Top severities: {top_severities}",
    ]
    return "\n".join(lines)


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


def test_keys_are_str_and_non_empty():
    data = load_data()
    for obj in data:
        for key in obj.keys():
            assert isinstance(key, str)
            assert key.strip()


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


def test_no_duplicate_entries():
    data = load_data()
    tuples = [(obj["Facility"], obj["Error Code"], obj["Severity"]) for obj in data]
    assert len(tuples) == len(set(tuples))


def test_keys_are_non_empty_strings():
    data = load_data()
    for obj in data:
        for key in obj.keys():
            assert isinstance(key, str) and key.strip()


def test_summary_contains_quality_metrics():
    summary = summarize_data()
    assert "Total entries" in summary
    assert re.search(r"Facilities: \d+ unique", summary)
    assert "Duplicate entries" in summary
    assert "Null/empty fields" in summary
    assert "Top facilities" in summary
    assert "Top severities" in summary
    # spot-check known counts
    assert "Duplicate entries: 0" in summary
    assert "Null/empty fields: 3" in summary
    assert "AT(70)" in summary
    assert "3(290)" in summary


if __name__ == "__main__":
    print(summarize_data())
