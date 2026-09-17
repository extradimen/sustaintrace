import hashlib

from esg_reliable_discovery.repair_dispatch import prepare_execution_request


def strategy():
    return {
        "strategy_id": "RS-AUTO",
        "execution_policy": "automatic",
        "risk_level": "low",
        "maturity": "unseen_validated",
        "rollback": "delete derived output",
    }


def test_dispatch_blocks_existing_plan_without_frozen_execution_contract(tmp_path):
    plan = {
        "plan_id": "plan-1",
        "failure_record_id": "failure-1",
        "decision": "automatic_candidate",
    }
    validation = {"validation_status": "ready_not_executed", "execution_performed": False}
    executor = {"executor_id": "RX-1", "status": "enabled"}
    result = prepare_execution_request(plan, validation, strategy(), executor, tmp_path)
    assert result["decision"] == "blocked"
    assert "frozen_execution_contract_missing" in result["blocking_reasons"]
    assert result["execution_state"] is None


def test_dispatch_builds_planned_state_only_for_hash_locked_contract(tmp_path):
    input_path = tmp_path / "input.json"
    expected_path = tmp_path / "expected.json"
    input_path.write_text("input\n")
    expected_path.write_text("expected\n")
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    plan = {
        "plan_id": "plan-1",
        "failure_record_id": "failure-1",
        "decision": "automatic_candidate",
        "execution_contract": {
            "input_artifact": "input.json",
            "input_sha256": digest(input_path),
            "expected_output_artifact": "expected.json",
            "expected_output_sha256": digest(expected_path),
            "validator_id": "validator-1",
            "invariants": ["parent_unchanged", "schema_valid"],
        },
    }
    validation = {"validation_status": "ready_not_executed", "execution_performed": False}
    executor = {"executor_id": "RX-1", "status": "enabled"}
    result = prepare_execution_request(plan, validation, strategy(), executor, tmp_path)
    assert result["decision"] == "ready_for_execution"
    assert result["execution_started"] is False
    assert result["execution_state"]["state"] == "planned"


def test_dispatch_rejects_tampered_input_hash(tmp_path):
    input_path = tmp_path / "input.json"
    expected_path = tmp_path / "expected.json"
    input_path.write_text("input\n")
    expected_path.write_text("expected\n")
    expected_sha = hashlib.sha256(expected_path.read_bytes()).hexdigest()
    plan = {
        "plan_id": "plan-1",
        "failure_record_id": "failure-1",
        "decision": "automatic_candidate",
        "execution_contract": {
            "input_artifact": "input.json",
            "input_sha256": "0" * 64,
            "expected_output_artifact": "expected.json",
            "expected_output_sha256": expected_sha,
            "validator_id": "validator-1",
            "invariants": ["parent_unchanged"],
        },
    }
    validation = {"validation_status": "ready_not_executed", "execution_performed": False}
    executor = {"executor_id": "RX-1", "status": "enabled"}
    result = prepare_execution_request(plan, validation, strategy(), executor, tmp_path)
    assert result["decision"] == "blocked"
    assert "frozen_input_hash_invalid" in result["blocking_reasons"]
