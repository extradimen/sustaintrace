import hashlib

from esg_reliable_discovery.evidence_contract_validation import validate_contract_fixture


def test_fixture_fails_closed_when_required_inputs_are_missing(tmp_path):
    parent = tmp_path / "parent.json"
    parent.write_text("parent\n")
    digest = hashlib.sha256(parent.read_bytes()).hexdigest()
    failure = {
        "record_id": "failure-1",
        "provenance": {"source_artifact": "parent.json", "source_sha256": digest},
    }
    contract = {
        "contract_id": "ERC-ONE-V01",
        "required_inputs": ["parent_failure_hash", "frozen_evidence_packet"],
        "execution_policy": "supervised",
        "candidate_output_rewrite_allowed": False,
        "rollback": "preserve parent",
    }
    binding = {
        "contract_id": "ERC-ONE-V01",
        "causal_subtype": "test",
        "candidate_output_rewrite_allowed": False,
        "execution_performed": False,
    }
    result = validate_contract_fixture(
        failure=failure,
        binding=binding,
        contract=contract,
        input_bindings={
            "parent_failure_hash": {"path": "parent.json", "sha256": digest}
        },
        root=tmp_path,
    )
    assert result["validation_status"] == "not_ready"
    assert result["missing_inputs"] == ["frozen_evidence_packet"]
    assert result["rollback_ledger"]["status"] == "prepared_not_executed"


def test_fixture_becomes_ready_only_when_every_hash_locked_input_passes(tmp_path):
    parent = tmp_path / "parent.json"
    evidence = tmp_path / "evidence.json"
    parent.write_text("parent\n")
    evidence.write_text("evidence\n")
    parent_hash = hashlib.sha256(parent.read_bytes()).hexdigest()
    evidence_hash = hashlib.sha256(evidence.read_bytes()).hexdigest()
    failure = {
        "record_id": "failure-1",
        "provenance": {"source_artifact": "parent.json", "source_sha256": parent_hash},
    }
    contract = {
        "contract_id": "ERC-ONE-V01",
        "required_inputs": ["parent_failure_hash", "frozen_evidence_packet"],
        "execution_policy": "supervised",
        "candidate_output_rewrite_allowed": False,
        "rollback": "preserve parent",
    }
    binding = {
        "contract_id": "ERC-ONE-V01",
        "causal_subtype": "test",
        "candidate_output_rewrite_allowed": False,
        "execution_performed": False,
    }
    result = validate_contract_fixture(
        failure=failure,
        binding=binding,
        contract=contract,
        input_bindings={
            "parent_failure_hash": {"path": "parent.json", "sha256": parent_hash},
            "frozen_evidence_packet": {"path": "evidence.json", "sha256": evidence_hash},
        },
        root=tmp_path,
    )
    assert result["validation_status"] == "ready_not_executed"
    assert all(result["checks"].values())
