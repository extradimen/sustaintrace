import pytest

from esg_reliable_discovery.v13_atomic_projection import (
    slot_output_schema,
    validate_and_project_slots,
)
from esg_reliable_discovery.v23_preflight import (
    calculation_binding_schema_v23,
    execute_calculation_plan_v23,
    ground_ordered_string_span_v23,
    validate_reference_direction_literals_v23,
)


def test_p13_reduction_magnitude_without_direction_is_rejected_before_candidate():
    contracts = [
        {
            "slot_id": "scope_1_2_2030_reduction_percent",
            "predicate_id": "esg_target::scope_1_2_reduction",
            "value_type": "number",
        }
    ]
    bindings = [
        {
            "slot_id": "scope_1_2_2030_reduction_percent",
            "reference_value": 90,
            "source_literal": "-90%",
        }
    ]
    with pytest.raises(ValueError, match="v23_reference_direction_literal_mismatch"):
        validate_reference_direction_literals_v23(contracts, bindings)


def test_p13_reduction_magnitude_with_decrease_direction_passes():
    contracts = [
        {
            "slot_id": "scope_1_2_2030_reduction_percent",
            "predicate_id": "esg_target::scope_1_2_reduction",
            "value_type": "number",
            "direction": "decrease",
        }
    ]
    bindings = [
        {
            "slot_id": "scope_1_2_2030_reduction_percent",
            "reference_value": 90,
            "source_literal": "-90%",
        }
    ]
    result = validate_reference_direction_literals_v23(contracts, bindings)
    assert result["status"] == "passed"


def test_calculation_operation_is_framework_owned_and_not_candidate_visible():
    plan = {
        "roles": [
            {"role_id": "scope_1", "unit": "tCO2e"},
            {"role_id": "scope_2", "unit": "tCO2e"},
            {"role_id": "scope_3", "unit": "tCO2e"},
            {"role_id": "reported_total", "unit": "tCO2e"},
        ],
        "steps": [
            {
                "step_id": "calculated_total",
                "operation": "sum",
                "inputs": ["scope_1", "scope_2", "scope_3"],
            },
            {
                "step_id": "difference",
                "operation": "difference",
                "inputs": ["calculated_total", "reported_total"],
            },
        ],
    }
    schema = calculation_binding_schema_v23(["E1", "E2", "E3", "E4"], plan)
    assert "operation" not in str(schema)
    evidence = [
        {"handle": "E1", "verbatim_text": "Scope 1 100,309"},
        {"handle": "E2", "verbatim_text": "Scope 2 23,849"},
        {"handle": "E3", "verbatim_text": "Scope 3 60,581,278"},
        {"handle": "E4", "verbatim_text": "Total 60,705,436"},
    ]
    values = [100309, 23849, 60581278, 60705436]
    output = {
        "observations": {
            role["role_id"]: {
                "value": value,
                "evidence_handle": f"E{index}",
                "period_year": 2025,
                "unit": "tCO2e",
            }
            for index, (role, value) in enumerate(
                zip(plan["roles"], values, strict=True), start=1
            )
        }
    }
    result = execute_calculation_plan_v23(output, evidence, plan)
    assert result["values"]["calculated_total"] == 60705436
    assert result["values"]["difference"] == 0


def test_safety_reconciliation_uses_frozen_multi_step_plan():
    plan = {
        "roles": [
            {"role_id": "employee_accidents", "unit": "count"},
            {"role_id": "temp_accidents", "unit": "count"},
            {"role_id": "employee_hours", "unit": "hours"},
            {"role_id": "temp_hours", "unit": "hours"},
        ],
        "steps": [
            {
                "step_id": "total_accidents",
                "operation": "sum",
                "inputs": ["employee_accidents", "temp_accidents"],
            },
            {
                "step_id": "total_hours",
                "operation": "sum",
                "inputs": ["employee_hours", "temp_hours"],
            },
            {
                "step_id": "ltir",
                "operation": "ratio_per_million",
                "inputs": ["total_accidents", "total_hours"],
            },
        ],
    }
    numbers = [79, 13, 295665967, 59563832]
    evidence = [
        {"handle": f"E{index}", "verbatim_text": str(value)}
        for index, value in enumerate(numbers, start=1)
    ]
    units = ["count", "count", "hours", "hours"]
    output = {
        "observations": {
            role["role_id"]: {
                "value": value,
                "evidence_handle": f"E{index}",
                "period_year": 2025,
                "unit": unit,
            }
            for index, (role, value, unit) in enumerate(
                zip(plan["roles"], numbers, units, strict=True), start=1
            )
        }
    }
    result = execute_calculation_plan_v23(output, evidence, plan)
    assert result["values"]["total_accidents"] == 92
    assert result["values"]["total_hours"] == 355229799
    assert result["values"]["ltir"] == pytest.approx(0.259, abs=0.0001)


def test_ordered_multi_handle_string_span_preserves_fragments():
    evidence = [
        {"handle": "E1", "verbatim_text": "nature, extent and timing are"},
        {"handle": "E2", "verbatim_text": "less than reasonable assurance"},
    ]
    result = ground_ordered_string_span_v23(
        value="nature, extent and timing are less than reasonable assurance",
        fragments=[
            {"evidence_handle": "E1", "verbatim_value": "nature, extent and timing are"},
            {"evidence_handle": "E2", "verbatim_value": "less than reasonable assurance"},
        ],
        evidence=evidence,
        required_terms=["timing", "reasonable assurance"],
    )
    assert result["evidence_handles"] == ["E1", "E2"]


def test_nonadjacent_string_span_fails_closed():
    evidence = [
        {"handle": "E1", "verbatim_text": "nature and extent"},
        {"handle": "E2", "verbatim_text": "unrelated"},
        {"handle": "E3", "verbatim_text": "less than reasonable assurance"},
    ]
    with pytest.raises(ValueError, match="v23_string_span_gap_exceeded"):
        ground_ordered_string_span_v23(
            value="nature and extent less than reasonable assurance",
            fragments=[
                {"evidence_handle": "E1", "verbatim_value": "nature and extent"},
                {
                    "evidence_handle": "E3",
                    "verbatim_value": "less than reasonable assurance",
                },
            ],
            evidence=evidence,
        )


def test_ordered_span_contract_runs_through_production_schema_and_projector():
    contract = {
        "slot_id": "limited_procedure_difference",
        "predicate_id": "esg_assurance::limited_procedure_difference",
        "value_type": "string",
        "string_input_shape": "ordered_span",
        "required_value_terms": ["timing", "reasonable assurance"],
    }
    evidence = [
        {"handle": "E1", "verbatim_text": "nature, extent and timing are"},
        {"handle": "E2", "verbatim_text": "less than reasonable assurance"},
    ]
    schema = slot_output_schema(["E1", "E2"], [contract])
    assert "fragments" in schema["properties"]["slots"]["items"]["oneOf"][0][
        "properties"
    ]
    output = {
        "slots": [
            {
                "slot_id": "limited_procedure_difference",
                "value": "nature, extent and timing are less than reasonable assurance",
                "fragments": [
                    {
                        "evidence_handle": "E1",
                        "verbatim_value": "nature, extent and timing are",
                    },
                    {
                        "evidence_handle": "E2",
                        "verbatim_value": "less than reasonable assurance",
                    },
                ],
            }
        ]
    }
    result = validate_and_project_slots(
        model_output=output,
        evidence=evidence,
        required_slots=[contract],
        framework_subject={"entity_id": "E", "entity_label": "Entity"},
    )
    assert result["validated_claims"][0]["evidence_handles"] == ["E1", "E2"]
