import pytest

from esg_reliable_discovery.v18_collection import project_grounded_collection
from esg_reliable_discovery.v18_period_binding import bind_multiyear_inputs


def test_p8_reporting_year_and_previous_year_bind_in_one_block():
    result = bind_multiyear_inputs(
        inputs=[
            {"value": 31.5, "period_year": 2025, "evidence_handle": "E1"},
            {"value": 31.7, "period_year": 2024, "evidence_handle": "E1"},
        ],
        evidence=[{
            "handle": "E1",
            "verbatim_text": (
                "Our 2025 gross emissions were 31.5 Mt CO2e, a reduction of "
                "0.2 Mt CO2e from the previous year."
            ),
        }],
        document_reporting_year=2025,
    )
    assert result["bindings"][1]["binding_rule"] == (
        "previous_year_relative_to_explicit_reporting_year"
    )


def test_p8_noncontiguous_scope3_categories_are_all_preserved():
    result = project_grounded_collection(
        members=[
            {
                "canonical_id": "scope3_11",
                "evidence_handle": "E11",
                "verbatim_value": "Category 11",
            },
            {
                "canonical_id": "scope3_8_12_13_14",
                "evidence_handle": "E8",
                "verbatim_value": "Category 8; Category 12; Category 13; Category 14",
            },
            {
                "canonical_id": "scope3_15",
                "evidence_handle": "E15",
                "verbatim_value": "Category 15",
            },
        ],
        evidence=[
            {"handle": "E11", "verbatim_text": "Category 11 (Use of sold products)"},
            {"handle": "E8", "verbatim_text": "Category 8; Category 12; Category 13; Category 14"},
            {"handle": "E15", "verbatim_text": "Category 15 (Investments)"},
        ],
    )
    assert result["member_count"] == 3
    assert result["canonical_ids"] == ["scope3_11", "scope3_8_12_13_14", "scope3_15"]


def test_collection_rejects_duplicate_canonical_members():
    with pytest.raises(ValueError, match="v18_duplicate_canonical_member"):
        project_grounded_collection(
            members=[
                {"canonical_id": "x", "evidence_handle": "E1", "verbatim_value": "one"},
                {"canonical_id": "x", "evidence_handle": "E2", "verbatim_value": "two"},
            ],
            evidence=[
                {"handle": "E1", "verbatim_text": "one"},
                {"handle": "E2", "verbatim_text": "two"},
            ],
        )
