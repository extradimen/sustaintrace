from esg_reliable_discovery.v1_period_context import add_auditable_period_context


def item(handle: str, text: str) -> dict:
    return {"handle": handle, "verbatim_text": text, "normalized_text": text}


def test_links_explicit_adjacent_end_date_to_value() -> None:
    handles = [
        item("M101-B0001", "Gross global Scope 1 emissions"),
        item("M101-B0002", "29930"),
        item("M101-B0003", "End date"),
        item("M101-B0004", "05/31/2024"),
    ]
    augmented, links = add_auditable_period_context(handles, 2025)
    assert augmented[1]["table_header_context"] == "2024"
    assert links[0]["rule"] == "same_page_within_two_blocks_explicit_end_date"


def test_links_reporting_year_label_to_frozen_manifest_year() -> None:
    handles = [
        item("M100-B0008", "Reporting year"),
        item("M100-B0009", "Gross global Scope 1 emissions"),
        item("M100-B0010", "27532"),
    ]
    augmented, links = add_auditable_period_context(handles, 2025)
    assert augmented[2]["table_header_context"] == "2025"
    assert links[0]["period_handle"] == "M100-B0008"


def test_does_not_link_distant_or_unlabelled_year() -> None:
    handles = [
        item("M100-B0001", "2021 baseline"),
        item("M100-B0004", "9376"),
    ]
    augmented, links = add_auditable_period_context(handles, 2025)
    assert "table_header_context" not in augmented[1]
    assert links == []
