from cisco_parser.parse_manual import normalize_soft_hyphens

def test_normalize_soft_hyphens():
    s = "in\u00advalid in-\nput Expla\ntion"
    out = normalize_soft_hyphens(s)
    assert "invalid" in out
    assert "input" in out
    # accept either spelling depending on upstream text layer
    assert ("Expla tion" in out) or ("Explanation" in out)
