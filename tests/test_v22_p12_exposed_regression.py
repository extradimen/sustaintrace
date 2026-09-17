import pytest

from esg_reliable_discovery.v22_preflight import dry_run_stage_b_contracts_v22


def test_p12_scalar_contract_without_predicate_is_rejected_before_candidate():
    contracts = [{"slot_id": "total_deaths", "value_type": "number"}]
    with pytest.raises(ValueError, match="v20_slot_contract_missing_fields"):
        dry_run_stage_b_contracts_v22(contracts)


def test_p12_object_contract_without_object_fields_is_rejected_before_candidate():
    contracts = [
        {
            "slot_id": "scope_1_2",
            "predicate_id": "esg::target",
            "value_type": "object",
            "member_contract": {"canonical_id": "nonempty_string"},
        }
    ]
    with pytest.raises(ValueError, match="v21_object_fields_missing"):
        dry_run_stage_b_contracts_v22(contracts)


def test_p12_array_without_member_contract_is_rejected_before_candidate():
    contracts = [
        {
            "slot_id": "reasonable_assurance_subjects",
            "predicate_id": "esg::assurance_subject",
            "value_type": "array",
        }
    ]
    with pytest.raises(ValueError, match="v20_collection_member_contract_missing"):
        dry_run_stage_b_contracts_v22(contracts)


def test_corrected_p12_shapes_execute_schema_and_projector_path():
    contracts = [
        {
            "slot_id": "total_deaths",
            "predicate_id": "esg::total_deaths",
            "value_type": "number",
        },
        {
            "slot_id": "target",
            "predicate_id": "esg::target",
            "value_type": "object",
            "member_contract": {"canonical_id": "nonempty_string"},
            "object_fields": [
                {"field_id": "base_year", "value_type": "number"},
                {"field_id": "target_year", "value_type": "number"},
            ],
        },
        {
            "slot_id": "assurance_subjects",
            "predicate_id": "esg::assurance_subject",
            "value_type": "array",
            "member_contract": {"canonical_id": "nonempty_string"},
            "collection_input_shape": "grounded_string_envelope",
        },
    ]
    result = dry_run_stage_b_contracts_v22(contracts)
    assert result["status"] == "passed"
    assert result["raw_contract_count"] == 3
    assert result["candidate_contract_count"] == 4
    assert result["validated_fixture_claim_count"] == 4
