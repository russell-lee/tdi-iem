import jsonschema
from cisco_parser.parse_manual import OUTPUT_SCHEMA

def test_schema_validation():
    sample = {
        "Raw Error Text": "%AAA-3-ACCT_IOMEM_LOW : msg",
        "Facility": "AAA",
        "Error Code": "ACCT_IOMEM_LOW",
        "Error Message": "msg",
        "Explanation": None,
        "Recommended Action": None,
        "Severity": 3,
        "Page": 2,
    }
    jsonschema.validate(sample, OUTPUT_SCHEMA)
