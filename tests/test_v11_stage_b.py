import json
from pathlib import Path

from esg_reliable_discovery.v11_stage_b import validate_and_project_v11

ONTOLOGY = json.loads(Path("configs/ontology/esg_atomic_claim_registry_v1.0.json").read_text())


def test_inherits_frozen_report_year_for_required_progress_observation() -> None:
    row = "Supply Chain Emissions | per unit | 9% reduction across all categories"
    evidence = [
        {
            "handle": "H1",
            "verbatim_text": row,
            "normalized_text": row,
            "table_header_context": "Progress",
        }
    ]
    output = {
        "claims": [
            {
                "metric_id": "supply_chain_emissions_intensity_reduction",
                "normalized_value": 9,
                "verbatim_value": "9%",
                "canonical_unit": "percent",
                "period_year": 2024,
                "scope_id": "pg_purchased_inputs",
                "claim_kind": "observed",
                "evidence_handle": "H1",
            }
        ]
    }
    result = validate_and_project_v11(
        output,
        evidence,
        ONTOLOGY,
        {"entity_id": "E", "entity_label": "P&G"},
        [
            {
                "metric_id": "supply_chain_emissions_intensity_reduction",
                "period_year": 2024,
                "claim_kind": "observed",
            }
        ],
        2024,
    )
    assert result["reporting_year_inheritance"][0]["period_year"] == 2024


def test_does_not_override_competing_explicit_year() -> None:
    evidence = [
        {
            "handle": "H1",
            "verbatim_text": "Supply Chain Emissions | per unit | 9% reduction from 2020",
            "normalized_text": "Supply Chain Emissions | per unit | 9% reduction from 2020",
            "table_header_context": "Progress",
        }
    ]
    output = {
        "claims": [
            {
                "metric_id": "supply_chain_emissions_intensity_reduction",
                "normalized_value": 9,
                "verbatim_value": "9%",
                "canonical_unit": "percent",
                "period_year": 2024,
                "scope_id": "pg_purchased_inputs",
                "claim_kind": "observed",
                "evidence_handle": "H1",
            }
        ]
    }
    try:
        validate_and_project_v11(
            output,
            evidence,
            ONTOLOGY,
            {"entity_id": "E", "entity_label": "P&G"},
            [
                {
                    "metric_id": "supply_chain_emissions_intensity_reduction",
                    "period_year": 2024,
                    "claim_kind": "observed",
                }
            ],
            2024,
        )
    except ValueError as error:
        assert "stage_b_period_not_grounded" in str(error)
    else:
        raise AssertionError("Competing explicit year must not be overridden")
