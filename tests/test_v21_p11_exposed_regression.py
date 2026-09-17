import pytest

from esg_reliable_discovery.v21_calculation import finalize_calculation_v21
from esg_reliable_discovery.v21_contract_adapters import (
    flatten_object_contracts,
    validate_and_project_slots_v21,
)


def test_grounded_string_collection_envelope_is_structurally_lowered():
    evidence = [
        {
            "handle": "M178-B0001",
            "verbatim_text": "operating hours per year and power demand of a product",
        }
    ]
    contracts = [
        {
            "slot_id": "assumptions",
            "predicate_id": "esg::assumptions",
            "value_type": "array",
            "member_contract": {"canonical_id": "string"},
            "collection_input_shape": "grounded_string_envelope",
        }
    ]
    output = {
        "slots": [
            {
                "slot_id": "assumptions",
                "value": ["operating hours per year", "power demand of a product"],
                "verbatim_value": "operating hours per year and power demand of a product",
                "evidence_handle": "M178-B0001",
            }
        ]
    }
    result = validate_and_project_slots_v21(
        model_output=output,
        evidence=evidence,
        required_slots=contracts,
        framework_subject={"entity_id": "siemens", "entity_label": "Siemens"},
    )
    assert result["v21_structural_adapters"] == ["assumptions"]
    assert len(result["validated_claims"]) == 2
    assert result["candidate_semantics_modified"] is False


def test_object_contract_is_flattened_before_candidate():
    contracts = [
        {
            "slot_id": "siemens_group",
            "predicate_id": "esg::target",
            "value_type": "object",
            "member_contract": {"canonical_id": "string"},
            "object_fields": [
                {"field_id": "target_percent", "value_type": "number"},
                {"field_id": "target_year", "value_type": "number"},
            ],
        }
    ]
    flattened = flatten_object_contracts(contracts)
    assert [item["slot_id"] for item in flattened] == [
        "siemens_group::target_percent",
        "siemens_group::target_year",
    ]
    assert all(item["value_type"] == "number" for item in flattened)


def test_sum_with_grounded_comparison_value_is_supported():
    evidence = [
        {
            "handle": "M176-B0001",
            "source_id": "s",
            "page": 176,
            "normalized_text": "288.3",
            "verbatim_text": "288.3",
        },
        {
            "handle": "M177-B0001",
            "source_id": "s",
            "page": 177,
            "normalized_text": "70.7",
            "verbatim_text": "70.7",
        },
        {
            "handle": "M176-B0002",
            "source_id": "s",
            "page": 176,
            "normalized_text": "359",
            "verbatim_text": "359",
        },
    ]

    def obs(value, handle, metric):
        return {
            "value": value,
            "evidence_handle": handle,
            "metric": metric,
            "period_year": "2025",
            "unit": "ktCO2e",
        }

    output = {
        "calculation_request": {
            "operation": "sum",
            "inputs": [obs(288.3, "M176-B0001", "Scope 1"), obs(70.7, "M177-B0001", "Scope 2")],
            "comparison_value": obs(359, "M176-B0002", "disclosed total"),
        }
    }
    result = finalize_calculation_v21(output, evidence)
    assert result["deterministic_calculation"]["result"] == pytest.approx(359)
    assert result["deterministic_calculation"]["recomputed_minus_disclosed"] == pytest.approx(0)


def test_missing_required_qualifier_fails_closed():
    evidence = [
        {
            "handle": "M160-B0001",
            "verbatim_text": "includes the value chain based on materiality considerations",
        }
    ]
    contracts = [
        {
            "slot_id": "boundary",
            "predicate_id": "esg::boundary",
            "value_type": "string",
            "required_qualifier_literals": ["based on materiality considerations"],
        }
    ]
    output = {
        "slots": [
            {
                "slot_id": "boundary",
                "value": "includes the value chain",
                "verbatim_value": "includes the value chain",
                "evidence_handle": "M160-B0001",
            }
        ]
    }
    with pytest.raises(ValueError, match="v21_required_qualifier_missing"):
        validate_and_project_slots_v21(
            model_output=output,
            evidence=evidence,
            required_slots=contracts,
            framework_subject={"entity_id": "siemens", "entity_label": "Siemens"},
        )
