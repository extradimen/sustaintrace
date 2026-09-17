import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_unit_repairs_require_both_bound_quote_and_native_pdf_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/unit_attachment_repairs.jsonl"
    if not path.exists():
        return
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    for item in records:
        assert item["validation"]["marker_in_bound_quote"] is True
        assert item["validation"]["marker_in_native_pdf_page"] is True
        assert item["fact_source_modified"] is False
        assert item["promotion_performed"] is False
