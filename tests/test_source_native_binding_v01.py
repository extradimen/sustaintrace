from esg_reliable_discovery.source_native_binding import bind_source_native_field


def _fact(value=486):
    return {
        "record_id": "fact-000000000000000000000001",
        "subject": {"task_id": "P23-GHG-CALC-001"},
        "value": value,
    }


def _qualification(matches):
    return {"table_cell_binding": {"matches": matches}}


def test_unique_native_context_requires_value_and_labels():
    result = bind_source_native_field(
        _fact(),
        _qualification([{"row": "Operational total", "column": "2025"}]),
        "Operational total   2025   486\nOther row          2025   12",
        pdf_path="report.pdf",
        pdf_page=78,
        context_radius=0,
    )
    assert result["status"] == "unique_context_binding"
    assert result["promotion_eligible"] is False


def test_value_without_local_labels_stays_incomplete():
    result = bind_source_native_field(
        _fact(),
        _qualification([{"row": "Operational total", "column": "2025"}]),
        "Different table row 486",
        pdf_path="report.pdf",
        pdf_page=78,
        context_radius=0,
    )
    assert result["status"] == "label_context_incomplete"


def test_unavailable_native_text_fails_closed():
    result = bind_source_native_field(
        _fact(),
        _qualification([]),
        None,
        pdf_path=None,
        pdf_page=78,
    )
    assert result["status"] == "unavailable"
    assert result["candidates"] == []
