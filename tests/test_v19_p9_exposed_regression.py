import pytest

from esg_reliable_discovery.v19_composite_subjects import (
    project_composite_assurance_subjects,
)
from esg_reliable_discovery.v19_prefreeze_audit import (
    audit_reference_before_candidate,
)
from esg_reliable_discovery.v19_table_period import bind_table_column_periods


def test_p9_methane_reference_page_outside_task_window_is_rejected():
    reference = {
        "normalized_value": {"gross_methane_2025_kt_ch4": 22.5},
        "evidence": [{"pdf_page": 351, "quote": "Gross methane emissions 22.5"}],
    }
    with pytest.raises(ValueError, match="v19_reference_page_outside_window:351"):
        audit_reference_before_candidate(
            target_pages=[181, 338],
            reference=reference,
            frozen_page_text={181: "targets", 338: "risks"},
            required_normalized_fields=["gross_methane_2025_kt_ch4"],
        )


def test_p9_calc_values_bind_to_explicit_table_column_years():
    result = bind_table_column_periods(
        inputs=[
            {"value": 33, "period_year": 2025, "evidence_handle": "C25"},
            {"value": 34, "period_year": 2024, "evidence_handle": "C24"},
        ],
        cells=[
            {
                "handle": "C25",
                "row_header": "Operated Scope 1+2 emissions",
                "column_header": "2025",
                "verbatim_value": "33",
            },
            {
                "handle": "C24",
                "row_header": "Operated Scope 1+2 emissions",
                "column_header": "2024",
                "verbatim_value": "34",
            },
        ],
        required_years=[2025, 2024],
    )
    assert result["two_dimensional_grounding"] is True
    assert result["bindings"][1]["column_header"] == "2024"


def test_p9_assurance_subjects_are_independently_grounded():
    result = project_composite_assurance_subjects(
        subjects=[
            {
                "canonical_id": "scope_1",
                "assurance_level": "reasonable",
                "evidence_handle": "E1",
                "verbatim_value": "Scope 1 emissions",
            },
            {
                "canonical_id": "scope_2",
                "assurance_level": "reasonable",
                "evidence_handle": "E2",
                "verbatim_value": "Scope 2 emissions",
            },
            {
                "canonical_id": "methane",
                "assurance_level": "reasonable",
                "evidence_handle": "E3",
                "verbatim_value": "Methane emissions",
            },
        ],
        evidence=[
            {"handle": "E1", "verbatim_text": "Gross Scope 1 emissions"},
            {"handle": "E2", "verbatim_text": "Gross Scope 2 emissions"},
            {"handle": "E3", "verbatim_text": "Gross Methane emissions"},
        ],
    )
    assert result["member_count"] == 3
    assert all(member["assurance_level"] == "reasonable" for member in result["members"])


def test_table_period_binding_rejects_wrong_column():
    with pytest.raises(ValueError, match="v19_column_year_not_grounded"):
        bind_table_column_periods(
            inputs=[{"value": 33, "period_year": 2025, "evidence_handle": "C24"}],
            cells=[{
                "handle": "C24",
                "row_header": "Operated Scope 1+2 emissions",
                "column_header": "2024",
                "verbatim_value": "33",
            }],
            required_years=[2025],
        )


def test_p9_wrong_safety_quote_is_rejected_before_candidate():
    reference = {
        "normalized_value": {"trir_2025": 0.47},
        "evidence": [{"pdf_page": 171, "quote": "TRIR 2025 0.47"}],
    }
    with pytest.raises(ValueError, match="v19_reference_quote_not_grounded:171"):
        audit_reference_before_candidate(
            target_pages=[171],
            reference=reference,
            frozen_page_text={171: "TRIR 2025 0.25 and 2024 0.25"},
            required_normalized_fields=["trir_2025"],
        )


def test_complete_grounded_reference_releases_inference_gate():
    reference = {
        "normalized_value": {"reported_2025_mtco2e": 335},
        "evidence": [{"pdf_page": 351, "quote": "Category 11 emissions = 335 Mt CO2e"}],
    }
    result = audit_reference_before_candidate(
        target_pages=[351],
        reference=reference,
        frozen_page_text={351: "Scope 3 Category 11 emissions = 335 Mt CO2e"},
        required_normalized_fields=["reported_2025_mtco2e"],
    )
    assert result["candidate_inference_released"] is True


def test_ordered_ellipsis_quote_supports_table_row_grounding():
    reference = {
        "normalized_value": {"reported": 69},
        "evidence": [{
            "pdf_page": 369,
            "quote": "Gross Scope 1 GHG emissions ... 2025 69 ... 2024 73",
        }],
    }
    result = audit_reference_before_candidate(
        target_pages=[369],
        reference=reference,
        frozen_page_text={369: "Gross Scope 1 GHG emissions unit 2025 69 2024 73"},
        required_normalized_fields=["reported"],
    )
    assert result["candidate_inference_released"] is True


def test_ordered_ellipsis_quote_rejects_reversed_table_fragments():
    reference = {
        "normalized_value": {"reported": 69},
        "evidence": [{
            "pdf_page": 369,
            "quote": "Gross Scope 1 GHG emissions ... 2025 69 ... 2024 73",
        }],
    }
    with pytest.raises(ValueError, match="v19_reference_quote_not_grounded:369"):
        audit_reference_before_candidate(
            target_pages=[369],
            reference=reference,
            frozen_page_text={369: "Gross Scope 1 GHG emissions 2024 73 2025 69"},
            required_normalized_fields=["reported"],
        )
