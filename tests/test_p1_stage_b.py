import pytest
from jsonschema import Draft202012Validator

from esg_reliable_discovery.p1_stage_b import (
    stage_b_schema,
    validate_and_project_stage_b,
)

ONTOLOGY = {
    "metrics": {"scope_1_methane_emissions": {
        "label": "Scope 1 methane emissions",
        "allowed_units": ["million_metric_tons_co2e"],
        "allowed_scopes": ["financial_control"],
    }},
    "units": {"million_metric_tons_co2e": {"label": "million metric tons CO2e"}},
    "scopes": {"financial_control": {"label": "financial control"}},
}
EVIDENCE = [{
    "handle": "M200-T0001-R0008",
    "verbatim_text": "CH4 (methane) | 0.027 | 0.022",
    "table_header_context": "Indicator | 2024 | 2023",
}]
OUTPUT = {"claims": [{
    "metric_id": "scope_1_methane_emissions",
    "normalized_value": 0.027,
    "verbatim_value": "0.027",
    "canonical_unit": "million_metric_tons_co2e",
    "period_year": 2024,
    "scope_id": "financial_control",
    "claim_kind": "observed",
    "evidence_handle": "M200-T0001-R0008",
}]}


def test_stage_b_schema_is_closed_and_handle_constrained():
    schema = stage_b_schema(["M200-T0001-R0008"], ONTOLOGY)
    assert not list(Draft202012Validator(schema).iter_errors(OUTPUT))
    bad = {"claims": [{**OUTPUT["claims"][0], "evidence_handle": "UNKNOWN"}]}
    assert list(Draft202012Validator(schema).iter_errors(bad))


def test_stage_b_validates_and_projects_graph():
    result = validate_and_project_stage_b(
        OUTPUT, EVIDENCE, ONTOLOGY,
        {"entity_id": "ENTITY::BASF-AR-2024", "entity_label": "BASF SE"},
    )
    assert result["validated_claims"][0]["field_support"]["normalized_value"] == (
        "deterministically_grounded"
    )
    assert len(result["knowledge_graph"]["nodes"]) == 3
    assert len(result["knowledge_graph"]["edges"]) == 2
    assert result["human_validation_claimed"] is False
    assert result["knowledge_graph"]["nodes"][0]["label"] == "BASF SE"
    observation = next(
        node for node in result["knowledge_graph"]["nodes"]
        if node["type"] == "observation"
    )
    assert observation["claim_kind"] == "observed"


def test_stage_b_rejects_ungrounded_value():
    bad = {"claims": [{**OUTPUT["claims"][0], "normalized_value": 0.99}]}
    with pytest.raises(ValueError, match="numeric_value_not_grounded"):
        validate_and_project_stage_b(bad, EVIDENCE, ONTOLOGY, {
            "entity_id": "ENTITY::BASF-AR-2024", "entity_label": "BASF SE"
        })


def test_stage_b_rejects_ungrounded_period():
    bad = {"claims": [{**OUTPUT["claims"][0], "period_year": 2022}]}
    with pytest.raises(ValueError, match="period_not_grounded"):
        validate_and_project_stage_b(bad, EVIDENCE, ONTOLOGY, {
            "entity_id": "ENTITY::BASF-AR-2024", "entity_label": "BASF SE"
        })


def test_stage_b_rejects_metric_unit_mismatch():
    ontology = {**ONTOLOGY, "units": {**ONTOLOGY["units"], "percent": {}}}
    bad = {"claims": [{**OUTPUT["claims"][0], "canonical_unit": "percent"}]}
    with pytest.raises(ValueError, match="unit_not_allowed"):
        validate_and_project_stage_b(bad, EVIDENCE, ontology, {
            "entity_id": "ENTITY::BASF-AR-2024", "entity_label": "BASF SE"
        })
