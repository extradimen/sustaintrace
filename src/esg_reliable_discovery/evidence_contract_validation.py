from __future__ import annotations

from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id


def validate_contract_fixture(
    *,
    failure: dict[str, Any],
    binding: dict[str, Any],
    contract: dict[str, Any],
    input_bindings: dict[str, dict[str, str]],
    root: Path,
) -> dict[str, Any]:
    required = set(contract["required_inputs"])
    supplied = set(input_bindings)
    missing = sorted(required - supplied)
    unexpected = sorted(supplied - required)
    hash_checks: dict[str, bool] = {}
    for name, artifact in input_bindings.items():
        path = root / artifact["path"]
        hash_checks[name] = path.is_file() and sha256_file(path) == artifact["sha256"]
    parent = failure["provenance"]
    parent_path = root / parent["source_artifact"]
    checks = {
        "contract_matches_binding": binding.get("contract_id") == contract["contract_id"],
        "parent_source_hash_valid": (
            parent_path.is_file() and sha256_file(parent_path) == parent["source_sha256"]
        ),
        "all_required_inputs_supplied": not missing,
        "no_unexpected_inputs": not unexpected,
        "all_supplied_hashes_valid": bool(hash_checks) and all(hash_checks.values()),
        "candidate_output_rewrite_forbidden": (
            binding.get("candidate_output_rewrite_allowed") is False
            and contract["candidate_output_rewrite_allowed"] is False
        ),
        "execution_not_started": binding.get("execution_performed") is False,
    }
    ready = all(checks.values()) and contract["execution_policy"] != "blocked"
    identity = {
        "failure_record_id": failure["record_id"],
        "contract_id": contract["contract_id"],
        "input_bindings": input_bindings,
    }
    return {
        "schema_version": "0.1",
        "record_kind": "evidence_contract_validation_fixture",
        "validation_id": stable_id("evidence-validation", identity),
        "failure_record_id": failure["record_id"],
        "contract_id": contract["contract_id"],
        "causal_subtype": binding["causal_subtype"],
        "validation_status": "ready_not_executed" if ready else "not_ready",
        "checks": checks,
        "missing_inputs": missing,
        "unexpected_inputs": unexpected,
        "input_hash_checks": hash_checks,
        "execution_performed": False,
        "rollback_ledger": {
            "parent_artifact": parent["source_artifact"],
            "parent_sha256": parent["source_sha256"],
            "status": "prepared_not_executed",
            "rollback_action": contract["rollback"],
        },
    }


def validate_stage_b_projection_lineage(
    *,
    task_id: str,
    stage_a: dict[str, Any],
    stage_b_context: dict[str, Any],
    projected_output: dict[str, Any],
    projection_validation: dict[str, Any],
) -> dict[str, Any]:
    resolved_handles = {
        item["source_handle"] for item in stage_a.get("resolved_evidence", [])
    }
    selected_handles = set(stage_b_context.get("selected_evidence_handles", []))
    slots = {
        item["slot_id"]: item for item in stage_b_context.get("required_slot_contracts", [])
    }
    claims = projected_output.get("validated_claims", [])
    claim_slots = {item.get("slot_id") for item in claims}
    frozen_fields = {
        "canonical_unit",
        "comparison_operator",
        "direction",
        "period",
        "predicate_id",
        "scope_id",
    }
    checks = {
        "task_identity_matches": stage_b_context.get("task_id") == task_id,
        "stage_a_evidence_supported": stage_a.get("framework_evidence_state") == "supported",
        "selected_handles_resolved_by_stage_a": bool(selected_handles)
        and selected_handles <= resolved_handles,
        "required_slots_projected_exactly": bool(slots) and claim_slots == set(slots),
        "claim_handles_selected": bool(claims)
        and all(item.get("evidence_handle") in selected_handles for item in claims),
        "semantic_fields_owned_by_frozen_contract": bool(claims)
        and all(
            all(
                item.get("field_ownership", {}).get(field) == "frozen_slot_contract"
                for field in frozen_fields
            )
            for item in claims
        ),
        "model_output_not_modified": projected_output.get("model_output_modified") is False,
        "posthoc_semantic_repair_absent": (
            projected_output.get("posthoc_semantic_repair_applied") is False
        ),
        "task_coverage_complete": projected_output.get("task_coverage", {}).get("complete")
        is True,
        "projection_validation_passed": (
            projection_validation.get("status") == "passed"
            and not projection_validation.get("errors")
        ),
    }
    return {
        "schema_version": "0.1",
        "record_kind": "stage_b_projection_lineage_validation",
        "task_id": task_id,
        "status": "validated_development_lineage" if all(checks.values()) else "not_ready",
        "checks": checks,
        "execution_performed_in_current_phase": False,
        "historical_outputs_modified": False,
        "reference_used_as_candidate_input": False,
    }
