from cisco_parser.parse_manual import extract_labeled_sections

def test_extract_labels_simple():
    body = "Explanation: foo\nMore details\nRecommended Action: bar"
    exp, rec = extract_labeled_sections(body)
    assert "foo" in exp and "More details" in exp
    assert rec == "bar"

def test_extract_labels_fuzzy():
    body = "Expla tion: fuzzy label works\nRecommended  Action: fix it"
    exp, rec = extract_labeled_sections(body)
    assert "fuzzy label works" in exp
    assert "fix it" in rec
