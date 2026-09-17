from esg_reliable_discovery.knowledge_base import audit_native_page_corroboration


def test_native_pdf_corroborates_scalar_and_cell_labels():
    fact = {
        "record_id": "fact-" + "a" * 24,
        "subject": {"task_id": "P99"},
        "value": 12.5,
    }
    qualification = {
        "table_cell_binding": {
            "matches": [{"pdf_page": 4, "row": "Total energy", "column": "2025"}]
        }
    }
    record = audit_native_page_corroboration(
        fact, qualification, "Total energy   2025   12.5", "report.pdf"
    )
    assert record["status"] == "passed_scalar_and_cell_labels"
    assert record["promotion_eligible"] is False


def test_native_pdf_corroboration_fails_closed_without_page():
    fact = {"record_id": "fact-" + "b" * 24, "subject": {"task_id": "P99"}, "value": 1}
    record = audit_native_page_corroboration(
        fact, {"table_cell_binding": {"matches": []}}, None, None
    )
    assert record["status"] == "unavailable_pdf_or_page"
