import hashlib

from esg_reliable_discovery.repair_execution import (
    RepairExecutionContext,
    initial_state,
    transition,
)
from esg_reliable_discovery.repair_operational import (
    canonical_json_bytes,
    execute_exact_handle_repair,
)


def preflight(expected):
    expected_sha = hashlib.sha256(canonical_json_bytes(expected)).hexdigest()
    state = initial_state(
        RepairExecutionContext(
            plan_id="plan-test",
            parent_record_id="failure-test",
            strategy_id="RS-EXACT-HANDLE-CANONICALIZATION",
            validator_id="validator-test",
            input_sha256="1" * 64,
            expected_output_sha256=expected_sha,
            rollback_action="delete derived output",
            invariants=(
                "archived_candidate_unchanged",
                "locked_parent_result_unchanged",
                "output_schema_valid",
            ),
        )
    )
    return transition(state, "preflight_passed", checks={"input_valid": True})[0]


def test_unknown_alias_rolls_back_without_derived_output():
    expected = {"decode_audit": {}, "decoded_output": {}}
    state, events, derived, error = execute_exact_handle_repair(
        preflight(expected),
        model_output={"evidence_handle": "H9999"},
        alias_catalog={"H0001": "M001-B0001"},
        expected_output=expected,
        invariant_results={
            "archived_candidate_unchanged": True,
            "locked_parent_result_unchanged": True,
            "output_schema_valid": True,
        },
    )
    assert state["state"] == "rolled_back"
    assert state["rollback_performed"] is True
    assert derived is None
    assert error == "ValueError:v31_unknown_evidence_alias:H9999"
    assert [event["to_state"] for event in events] == ["failed_execution", "rolled_back"]


def test_wrong_frozen_expected_output_rolls_back_after_postvalidation():
    expected = {"decode_audit": {}, "decoded_output": {}}
    state, events, derived, error = execute_exact_handle_repair(
        preflight(expected),
        model_output={"evidence_handle": "H0001", "value": 7},
        alias_catalog={"H0001": "M001-B0001"},
        expected_output=expected,
        invariant_results={
            "archived_candidate_unchanged": True,
            "locked_parent_result_unchanged": True,
            "output_schema_valid": True,
        },
    )
    assert state["state"] == "rolled_back"
    assert derived is not None
    assert error is None
    assert [event["to_state"] for event in events] == [
        "executed",
        "postvalidation_failed",
        "rolled_back",
    ]


def test_same_frozen_inputs_produce_same_execution_identity_and_bytes():
    expected = {
        "decode_audit": {
            "status": "passed",
            "emitted_aliases": ["H0001"],
            "decoded_handles": ["M001-B0001"],
            "approximate_handle_repair": False,
            "candidate_output_archived_unchanged": True,
            "semantic_values_modified": False,
        },
        "decoded_output": {"evidence_handle": "M001-B0001", "value": 7},
    }
    arguments = {
        "model_output": {"evidence_handle": "H0001", "value": 7},
        "alias_catalog": {"H0001": "M001-B0001"},
        "expected_output": expected,
        "invariant_results": {
            "archived_candidate_unchanged": True,
            "locked_parent_result_unchanged": True,
            "output_schema_valid": True,
        },
    }
    first = execute_exact_handle_repair(preflight(expected), **arguments)
    second = execute_exact_handle_repair(preflight(expected), **arguments)
    assert first[0]["execution_id"] == second[0]["execution_id"]
    assert canonical_json_bytes(first[2]) == canonical_json_bytes(second[2])
    assert first[0]["state"] == second[0]["state"] == "promoted"
