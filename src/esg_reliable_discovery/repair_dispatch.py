from __future__ import annotations

from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id
from esg_reliable_discovery.repair_execution import RepairExecutionContext, initial_state


class StageBHandleClosureError(ValueError):
    """Raised before model execution or knowledge write when Stage B escapes Stage A."""

    def __init__(self, audit: dict[str, Any]) -> None:
        self.audit = audit
        reasons = ",".join(audit["blocking_reasons"])
        super().__init__(f"stage_b_handle_closure_blocked:{reasons}")


def prepare_stage_b_handle_closure_dispatch(
    *,
    stage_a_output: dict[str, Any],
    stage_b_context: dict[str, Any],
    projected_output: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed unless every Stage B evidence handle belongs to Stage A's closure."""
    resolved = {
        item["source_handle"] for item in stage_a_output.get("resolved_evidence", [])
    }
    selected = set(stage_b_context.get("selected_evidence_handles", []))
    claims = projected_output.get("validated_claims", [])
    claim_handles = {item.get("evidence_handle") for item in claims}
    unresolved_selected = sorted(selected - resolved)
    unselected_claims = sorted(handle for handle in claim_handles - selected if handle)
    reasons = []
    if not resolved:
        reasons.append("stage_a_resolved_evidence_empty")
    if not selected:
        reasons.append("stage_b_selected_evidence_empty")
    if unresolved_selected:
        reasons.append("stage_b_selected_handle_outside_stage_a_closure")
    if unselected_claims:
        reasons.append("projected_claim_handle_not_selected")
    return {
        "schema_version": "0.1",
        "record_kind": "stage_b_handle_closure_dispatch",
        "task_id": stage_b_context.get("task_id"),
        "decision": "ready_for_supervised_projection" if not reasons else "blocked",
        "blocking_reasons": reasons,
        "stage_a_resolved_handles": sorted(resolved),
        "stage_b_selected_handles": sorted(selected),
        "unresolved_selected_handles": unresolved_selected,
        "unselected_claim_handles": unselected_claims,
        "execution_started": False,
        "candidate_output_rewritten": False,
    }


def enforce_stage_b_handle_closure(
    *,
    stage_a_output: dict[str, Any],
    stage_b_context: dict[str, Any],
    projected_output: dict[str, Any],
    gate_phase: str,
) -> dict[str, Any]:
    """Return an auditable gate record or raise before the requested boundary."""
    if gate_phase not in {"pre_model", "pre_knowledge_write"}:
        raise ValueError(f"invalid_stage_b_handle_closure_gate_phase:{gate_phase}")
    audit = prepare_stage_b_handle_closure_dispatch(
        stage_a_output=stage_a_output,
        stage_b_context=stage_b_context,
        projected_output=projected_output,
    )
    audit["gate_phase"] = gate_phase
    if audit["decision"] == "blocked":
        raise StageBHandleClosureError(audit)
    return audit


def restrict_projection_to_stage_a_closure(
    *,
    stage_a_output: dict[str, Any],
    stage_b_context: dict[str, Any],
    projected_output: dict[str, Any],
) -> dict[str, Any]:
    """Derive a partial view without inventing or remapping an out-of-closure claim."""
    resolved = {
        item["source_handle"] for item in stage_a_output.get("resolved_evidence", [])
    }
    required_slots = {
        item["slot_id"] for item in stage_b_context.get("required_slot_contracts", [])
    }
    retained = [
        item
        for item in projected_output.get("validated_claims", [])
        if item.get("evidence_handle") in resolved
    ]
    retained_slots = {item.get("slot_id") for item in retained}
    missing_slots = sorted(required_slots - retained_slots)
    return {
        "schema_version": "0.1",
        "record_kind": "stage_b_closure_restricted_projection",
        "task_id": stage_b_context.get("task_id"),
        "status": "complete" if not missing_slots else "partial_fail_closed",
        "retained_claims": retained,
        "missing_slots": missing_slots,
        "complete_projection_eligible": not missing_slots,
        "candidate_output_rewritten": False,
        "historical_output_modified": False,
        "execution_performed": False,
    }


def index_executors(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for executor in catalog.get("executors", []):
        strategy_id = executor["strategy_id"]
        if strategy_id in result:
            raise ValueError(f"duplicate executor for strategy: {strategy_id}")
        result[strategy_id] = executor
    return result


def prepare_execution_request(
    plan: dict[str, Any],
    validation: dict[str, Any],
    strategy: dict[str, Any],
    executor: dict[str, Any] | None,
    root: Path,
) -> dict[str, Any]:
    """Convert a validated automatic plan into a frozen request, or fail closed."""
    reasons: list[str] = []
    if plan.get("decision") != "automatic_candidate":
        reasons.append("plan_not_automatic_candidate")
    if validation.get("validation_status") != "ready_not_executed":
        reasons.append("candidate_validation_not_ready")
    if validation.get("execution_performed") is not False:
        reasons.append("candidate_already_executed")
    if strategy.get("execution_policy") != "automatic":
        reasons.append("strategy_not_automatic")
    if strategy.get("risk_level") != "low":
        reasons.append("strategy_not_low_risk")
    if strategy.get("maturity") != "unseen_validated":
        reasons.append("strategy_not_unseen_validated")
    if executor is None or executor.get("status") != "enabled":
        reasons.append("enabled_executor_missing")

    contract = plan.get("execution_contract")
    if not isinstance(contract, dict):
        reasons.append("frozen_execution_contract_missing")
        contract = {}
    required = {
        "input_artifact",
        "input_sha256",
        "expected_output_artifact",
        "expected_output_sha256",
        "validator_id",
        "invariants",
    }
    if set(contract) < required:
        reasons.append("frozen_execution_contract_incomplete")
    else:
        input_path = root / contract["input_artifact"]
        expected_path = root / contract["expected_output_artifact"]
        if not input_path.is_file() or sha256_file(input_path) != contract["input_sha256"]:
            reasons.append("frozen_input_hash_invalid")
        if (
            not expected_path.is_file()
            or sha256_file(expected_path) != contract["expected_output_sha256"]
        ):
            reasons.append("frozen_expected_output_hash_invalid")
        if not isinstance(contract["invariants"], list) or not contract["invariants"]:
            reasons.append("frozen_invariants_missing")

    identity = {
        "plan_id": plan.get("plan_id"),
        "validation_status": validation.get("validation_status"),
        "strategy_id": strategy.get("strategy_id"),
        "executor_id": executor.get("executor_id") if executor else None,
        "contract": contract,
    }
    dispatch = {
        "schema_version": "0.1",
        "record_kind": "repair_dispatch_decision",
        "dispatch_id": stable_id("repair-dispatch", identity),
        "plan_id": plan.get("plan_id"),
        "failure_record_id": plan.get("failure_record_id"),
        "strategy_id": strategy.get("strategy_id"),
        "executor_id": executor.get("executor_id") if executor else None,
        "decision": "ready_for_execution" if not reasons else "blocked",
        "blocking_reasons": reasons,
        "execution_started": False,
        "execution_state": None,
    }
    if reasons:
        return dispatch

    context = RepairExecutionContext(
        plan_id=plan["plan_id"],
        parent_record_id=plan["failure_record_id"],
        strategy_id=strategy["strategy_id"],
        validator_id=contract["validator_id"],
        input_sha256=contract["input_sha256"],
        expected_output_sha256=contract["expected_output_sha256"],
        rollback_action=strategy["rollback"],
        invariants=tuple(contract["invariants"]),
    )
    dispatch["execution_state"] = initial_state(context)
    return dispatch
