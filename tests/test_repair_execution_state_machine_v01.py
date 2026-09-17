import pytest

from esg_reliable_discovery.repair_execution import (
    InvalidRepairTransition,
    RepairExecutionContext,
    initial_state,
    postvalidate,
    transition,
)

HASH_A = "a" * 64
HASH_B = "b" * 64


def context():
    return RepairExecutionContext(
        plan_id="plan-test",
        parent_record_id="failure-test",
        strategy_id="RS-TEST",
        validator_id="BV-TEST",
        input_sha256=HASH_A,
        expected_output_sha256=HASH_B,
        rollback_action="delete derived output",
        invariants=("source_unchanged", "schema_valid"),
    )


def reach_executed():
    state = initial_state(context())
    state, _ = transition(state, "preflight_passed", checks={"input_hash_valid": True})
    state, _ = transition(state, "executed", checks={"command_exit_zero": True})
    return state


def test_positive_path_requires_postvalidation_before_promotion():
    state = reach_executed()
    with pytest.raises(InvalidRepairTransition, match="invalid repair transition"):
        transition(state, "promoted", checks={})
    state, _ = postvalidate(
        state,
        actual_output_sha256=HASH_B,
        invariant_results={"source_unchanged": True, "schema_valid": True},
    )
    state, _ = transition(state, "promoted", checks={"postvalidation_recorded": True})
    assert state["state"] == "promoted"
    assert state["promotion_performed"] is True
    assert state["rollback_performed"] is False


def test_output_hash_mismatch_forces_failure_then_rollback():
    state = reach_executed()
    state, event = postvalidate(
        state,
        actual_output_sha256=HASH_A,
        invariant_results={"source_unchanged": True, "schema_valid": True},
    )
    assert state["state"] == "postvalidation_failed"
    assert event["checks"]["output_sha256_matches"] is False
    state, _ = transition(state, "rolled_back", checks={"derived_output_deleted": True})
    assert state["rollback_performed"] is True


def test_failed_invariant_forces_rollback_and_missing_invariant_is_rejected():
    state = reach_executed()
    with pytest.raises(InvalidRepairTransition, match="every frozen invariant"):
        postvalidate(
            state,
            actual_output_sha256=HASH_B,
            invariant_results={"source_unchanged": True},
        )
    state, _ = postvalidate(
        state,
        actual_output_sha256=HASH_B,
        invariant_results={"source_unchanged": True, "schema_valid": False},
    )
    assert state["state"] == "postvalidation_failed"
    state, _ = transition(state, "rolled_back", checks={"rollback_verified": True})
    assert state["state"] == "rolled_back"


def test_execution_promotion_and_rollback_cannot_claim_success_with_failed_checks():
    state = initial_state(context())
    state, _ = transition(state, "preflight_passed", checks={"input_hash_valid": True})
    with pytest.raises(InvalidRepairTransition, match="failed checks"):
        transition(state, "executed", checks={"command_exit_zero": False})

    state = reach_executed()
    state, _ = postvalidate(
        state,
        actual_output_sha256=HASH_B,
        invariant_results={"source_unchanged": True, "schema_valid": True},
    )
    with pytest.raises(InvalidRepairTransition, match="failed checks"):
        transition(state, "promoted", checks={"overlay_written": False})

    state = reach_executed()
    state, _ = postvalidate(
        state,
        actual_output_sha256=HASH_A,
        invariant_results={"source_unchanged": True, "schema_valid": True},
    )
    with pytest.raises(InvalidRepairTransition, match="failed checks"):
        transition(state, "rolled_back", checks={"derived_output_deleted": False})
