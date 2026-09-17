import json
from pathlib import Path

import pytest

from esg_reliable_discovery.v1_stage_b import validate_and_project_v1

ONTOLOGY = json.loads(
    Path("configs/ontology/esg_atomic_claim_registry_v1.0.json").read_text(encoding="utf-8")
)
SUBJECT = {"entity_id": "ENTITY::TEST", "entity_label": "Test issuer"}


def evidence(text: str) -> list[dict]:
    return [
        {
            "handle": "H1",
            "verbatim_text": text,
            "normalized_text": text,
            "table_header_context": None,
        }
    ]


def claim(metric: str, value: float, verbatim: str, year: int, unit: str) -> dict:
    return {
        "claims": [
            {
                "metric_id": metric,
                "normalized_value": value,
                "verbatim_value": verbatim,
                "canonical_unit": unit,
                "period_year": year,
                "scope_id": "reported_boundary",
                "claim_kind": "observed",
                "evidence_handle": "H1",
            }
        ]
    }


def test_rejects_gm_scope_1_2_value_as_methane() -> None:
    text = (
        "Absolute Scope 1 and 2 Emissions. Greenhouse gases covered: CO2, CH4, N2O. "
        "2025 Status: 2.1M MTCO2e"
    )
    output = claim(
        "scope_1_methane_emissions",
        2.1,
        "2.1M MTCO2e",
        2025,
        "million_metric_tons_co2e",
    )
    with pytest.raises(ValueError, match="v1_metric_not_lexically_grounded"):
        validate_and_project_v1(output, evidence(text), ONTOLOGY, SUBJECT, [])


def test_accepts_combined_scope_1_2_metric_when_grounded() -> None:
    text = "Absolute Scope 1 and 2 Emissions. 2025 Status: 2.1M MTCO2e"
    output = claim(
        "combined_scope_1_2_emissions",
        2.1,
        "2.1M MTCO2e",
        2025,
        "million_metric_tons_co2e",
    )
    result = validate_and_project_v1(
        output,
        evidence(text),
        ONTOLOGY,
        SUBJECT,
        [{"metric_id": "combined_scope_1_2_emissions", "period_year": 2025}],
    )
    assert result["task_coverage"]["complete"] is True


def test_rejects_schema_valid_but_incomplete_projection() -> None:
    text = "In 2025, 100% sustainable electricity coverage across our sites."
    output = claim("renewable_power_share", 100, "100% sustainable electricity", 2025, "percent")
    with pytest.raises(ValueError, match="v1_required_claims_missing"):
        validate_and_project_v1(
            output,
            evidence(text),
            ONTOLOGY,
            SUBJECT,
            [
                {"metric_id": "renewable_power_share", "period_year": 2025},
                {"metric_id": "combined_scope_1_2_emissions", "period_year": 2025},
            ],
        )
