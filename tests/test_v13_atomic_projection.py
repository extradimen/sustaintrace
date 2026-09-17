import pytest

from esg_reliable_discovery.v13_atomic_projection import validate_and_project_slots

EVIDENCE = [
    {
        "handle": "E1",
        "verbatim_text": (
            "Operational control. Lenovo accounts for 100% of emissions from operations "
            "over which it has control."
        ),
    }
]
SUBJECT = {"entity_id": "LEI::LENOVO", "entity_label": "Lenovo Group Limited"}
SLOTS = [
    {
        "slot_id": "boundary_method",
        "predicate_id": "uses_organizational_boundary_method",
        "value_type": "string",
        "period": "FY2024/25",
        "scope_id": "ghg_inventory",
    },
    {
        "slot_id": "included_share",
        "predicate_id": "includes_controlled_operation_share",
        "value_type": "number",
        "canonical_unit": "percent",
        "period": "FY2024/25",
        "scope_id": "ghg_inventory",
    },
]


def test_framework_owned_slots_project_complete_narrative_claims() -> None:
    result = validate_and_project_slots(
        model_output={
            "slots": [
                {
                    "slot_id": "boundary_method",
                    "value": "operational control",
                    "verbatim_value": "Operational control",
                    "evidence_handle": "E1",
                },
                {
                    "slot_id": "included_share",
                    "value": 100,
                    "verbatim_value": "100%",
                    "evidence_handle": "E1",
                },
            ]
        },
        evidence=EVIDENCE,
        required_slots=SLOTS,
        framework_subject=SUBJECT,
    )
    assert result["task_coverage"]["complete"] is True
    assert result["validated_claims"][0]["predicate_id"] == (
        "uses_organizational_boundary_method"
    )
    assert result["validated_claims"][1]["canonical_unit"] == "percent"


def test_missing_slot_is_rejected() -> None:
    with pytest.raises(ValueError, match="v13_slot_schema_failure"):
        validate_and_project_slots(
            model_output={
                "slots": [
                    {
                        "slot_id": "boundary_method",
                        "value": "operational control",
                        "verbatim_value": "Operational control",
                        "evidence_handle": "E1",
                    }
                ]
            },
            evidence=EVIDENCE,
            required_slots=SLOTS,
            framework_subject=SUBJECT,
        )


def test_numeric_value_must_be_in_verbatim_evidence() -> None:
    output = {
        "slots": [
            {
                "slot_id": "boundary_method",
                "value": "operational control",
                "verbatim_value": "Operational control",
                "evidence_handle": "E1",
            },
            {
                "slot_id": "included_share",
                "value": 99,
                "verbatim_value": "100%",
                "evidence_handle": "E1",
            },
        ]
    }
    with pytest.raises(ValueError, match="v13_numeric_not_grounded"):
        validate_and_project_slots(
            model_output=output,
            evidence=EVIDENCE,
            required_slots=SLOTS,
            framework_subject=SUBJECT,
        )


def test_schema_enforces_each_contract_value_type() -> None:
    output = {
        "slots": [
            {
                "slot_id": "boundary_method",
                "value": "operational control",
                "verbatim_value": "Operational control",
                "evidence_handle": "E1",
            },
            {
                "slot_id": "included_share",
                "value": "one hundred",
                "verbatim_value": "100%",
                "evidence_handle": "E1",
            },
        ]
    }
    with pytest.raises(ValueError, match="v13_slot_schema_failure"):
        validate_and_project_slots(
            model_output=output,
            evidence=EVIDENCE,
            required_slots=SLOTS,
            framework_subject=SUBJECT,
        )


def test_framework_preserves_numeric_direction_and_comparator() -> None:
    slots = [
        {
            "slot_id": "change",
            "predicate_id": "reports_change",
            "value_type": "number",
            "canonical_unit": "percent",
            "direction": "decrease",
            "comparison_operator": "<",
        }
    ]
    result = validate_and_project_slots(
        model_output={
            "slots": [
                {
                    "slot_id": "change",
                    "value": 10.7,
                    "verbatim_value": "(10.7)%",
                    "evidence_handle": "E2",
                }
            ]
        },
        evidence=[{"handle": "E2", "verbatim_text": "change (10.7)%"}],
        required_slots=slots,
        framework_subject=SUBJECT,
    )
    claim = result["validated_claims"][0]
    assert claim["normalized_signed_value"] == -10.7
    assert claim["comparison_operator"] == "<"


def test_negative_decrease_is_grounded_by_parenthetical_source_value() -> None:
    slots = [
        {
            "slot_id": "change",
            "predicate_id": "reports_change",
            "value_type": "number",
            "canonical_unit": "percent",
            "direction": "decrease",
        }
    ]
    result = validate_and_project_slots(
        model_output={
            "slots": [
                {
                    "slot_id": "change",
                    "value": -10.7,
                    "verbatim_value": "(10.7)%",
                    "evidence_handle": "E2",
                }
            ]
        },
        evidence=[{"handle": "E2", "verbatim_text": "change (10.7)%"}],
        required_slots=slots,
        framework_subject=SUBJECT,
    )
    assert result["validated_claims"][0]["normalized_signed_value"] == -10.7


def test_numeric_string_is_deterministically_normalized_without_changing_model_output() -> None:
    slots = [
        {
            "slot_id": "emissions",
            "predicate_id": "reports_emissions",
            "value_type": "number",
            "canonical_unit": "tco2e",
        }
    ]
    model_output = {
        "slots": [
            {
                "slot_id": "emissions",
                "value": "13,891",
                "verbatim_value": "13,891",
                "evidence_handle": "E2",
            }
        ]
    }
    result = validate_and_project_slots(
        model_output=model_output,
        evidence=[{"handle": "E2", "verbatim_text": "13,891"}],
        required_slots=slots,
        framework_subject=SUBJECT,
    )
    claim = result["validated_claims"][0]
    assert claim["value"] == 13891
    assert claim["model_emitted_value"] == "13,891"
    assert model_output["slots"][0]["value"] == "13,891"
