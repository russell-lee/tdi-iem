from cisco_parser.parse_manual import parse_block

def test_parse_block_minimal():
    block = "%AAA-3-ACCT_IOMEM_LOW : AAA ACCT process suspended : low I/O memory\n" \            "Explanation: Something bad happened.\n" \            "Recommended Action: Do the thing."
    entry = parse_block(block, page_num=3)
    assert entry is not None
    out = entry.to_output()
    assert out["Facility"] == "AAA"
    assert out["Error Code"] == "ACCT_IOMEM_LOW"
    assert out["Severity"] == 3
    assert "Something bad happened" in out["Explanation"]
    assert "Do the thing" in out["Recommended Action"]
    assert out["Page"] == 3
