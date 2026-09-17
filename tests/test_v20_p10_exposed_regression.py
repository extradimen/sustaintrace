import pytest

from esg_reliable_discovery.v13_atomic_projection import (
    slot_output_schema,
    validate_and_project_slots,
)
from esg_reliable_discovery.v20_collection_projection import project_collection_slot
from esg_reliable_discovery.v20_contracts import (
    require_controlled_conflict_slots,
    validate_evidence_handle_pages,
    validate_slot_contracts_before_candidate,
)
from esg_reliable_discovery.v20_failure_taxonomy import classify_failure


def test_p10_missing_predicate_is_blocked_before_candidate():
    with pytest.raises(ValueError, match="v20_slot_contract_missing_fields:0:predicate_id"):
        validate_slot_contracts_before_candidate(
            [{"slot_id": "fatalities_2025", "value_type": "number"}]
        )


def test_collection_requires_member_contract_before_candidate():
    with pytest.raises(ValueError, match="v20_collection_member_contract_missing:criteria"):
        validate_slot_contracts_before_candidate(
            [{"slot_id": "criteria", "predicate_id": "has_criterion", "value_type": "array"}]
        )


def test_complete_collection_contract_releases_candidate():
    result = validate_slot_contracts_before_candidate(
        [{
            "slot_id": "criteria",
            "predicate_id": "has_criterion",
            "value_type": "array",
            "member_contract": {"canonical_id": "string", "verbatim_value": "string"},
        }]
    )
    assert result["candidate_inference_released"] is True


def test_object_members_become_independent_grounded_claims():
    result = project_collection_slot(
        slot_id="operational_control",
        predicate_id="reports_boundary_share",
        value_type="object",
        value={
            "subsidiaries_operated": {
                "evidence_handle": "E1",
                "verbatim_value": "Subsidiaries 100%",
            },
            "joint_operations_non_operated": {
                "evidence_handle": "E2",
                "verbatim_value": "Joint operations 0%",
            },
        },
        evidence=[
            {"handle": "E1", "verbatim_text": "Subsidiaries 100% operated"},
            {"handle": "E2", "verbatim_text": "Joint operations 0% non-operated"},
        ],
    )
    assert result["atomic_claim_count"] == 2
    assert result["atomic_claims"][1]["member_id"] == "joint_operations_non_operated"


def test_assurance_page_range_conflict_must_be_explicit():
    with pytest.raises(ValueError, match="v20_required_conflict_slots_missing"):
        require_controlled_conflict_slots(
            [{"slot_id": "page_range_introduction"}],
            ["page_range_introduction", "page_range_scope_statement", "range_conflict_status"],
        )


def test_native_array_slot_is_accepted_and_projected_atomically():
    contracts = [{
        "slot_id": "criteria",
        "predicate_id": "has_criterion",
        "value_type": "array",
        "member_contract": {"canonical_id": "string", "verbatim_value": "string"},
    }]
    output = {
        "slots": [{
            "slot_id": "criteria",
            "value": [
                {
                    "canonical_id": "esrs",
                    "evidence_handle": "E1",
                    "verbatim_value": "European Sustainability Reporting Standards",
                },
                {
                    "canonical_id": "taxonomy_article_8",
                    "evidence_handle": "E2",
                    "verbatim_value": "Article 8 of Regulation (EU) 2020/852",
                },
            ],
        }]
    }
    evidence = [
        {"handle": "E1", "verbatim_text": "European Sustainability Reporting Standards"},
        {"handle": "E2", "verbatim_text": "Article 8 of Regulation (EU) 2020/852"},
    ]
    schema = slot_output_schema(["E1", "E2"], contracts)
    assert schema["properties"]["slots"]["items"]["oneOf"][0]["required"] == [
        "slot_id",
        "value",
    ]
    result = validate_and_project_slots(
        model_output=output,
        evidence=evidence,
        required_slots=contracts,
        framework_subject={"entity_id": "ENTITY::SHELL", "entity_label": "Shell plc"},
    )
    assert len(result["validated_claims"]) == 2
    assert result["validated_claims"][1]["member_id"] == "taxonomy_article_8"


def test_p10_wrong_page_prefix_is_blocked_before_candidate():
    with pytest.raises(ValueError, match="v20_evidence_handle_page_mismatch:P370-B0017:369"):
        validate_evidence_handle_pages(
            [{"handle": "P370-B0017", "page": 369, "verbatim_text": "value"}]
        )


def test_transport_failure_is_not_scored_as_model_behavior():
    result = classify_failure(
        stage="stage_a",
        error_type="OllamaError",
        error_message="HTTP 502: read: operation timed out",
        model_call_started=True,
    )
    assert result["category"] == "cloud_transport"
    assert result["score_as_model_failure"] is False


def test_missing_predicate_is_owned_by_frozen_configuration():
    result = classify_failure(
        stage="stage_b",
        error_type="KeyError",
        error_message="predicate_id",
        model_call_started=False,
    )
    assert result["owner"] == "framework"
    assert result["retry_policy"] == "no_retry_in_locked_experiment"
