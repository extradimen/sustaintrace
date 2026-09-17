from __future__ import annotations

import json
from typing import Any

from esg_reliable_discovery.knowledge_base import stable_id


def classify_evidence_failure(failure: dict[str, Any]) -> str:
    signature = failure["failure_signature"]
    state_text = json.dumps(failure.get("observed_stage_states", {}), ensure_ascii=False).casefold()
    if signature == "TARGET_ASSURANCE_WINDOW_INCOMPLETE":
        return "assurance_window_incomplete"
    if signature == "EVIDENCE_SELECTION_GAP" and "year" in state_text:
        return "period_anchor_missing"
    if "rounded" in state_text:
        return "rounded_value_selected"
    if "abstain" in state_text:
        return "exact_value_present_but_abstained"
    if "truncated" in state_text:
        return "truncated_quote"
    if "stage_b" in state_text and "grounding" in state_text:
        return "stage_b_handle_binding_failure"
    return "unclassified_evidence_failure"


OPERATIONAL_DECISIONS = {
    "assurance_window_incomplete": "supervised_new_lineage_reselection",
    "period_anchor_missing": "supervised_new_lineage_reselection",
    "rounded_value_selected": "supervised_exact_cell_binding",
    "exact_value_present_but_abstained": "supervised_exact_cell_binding",
    "stage_b_handle_binding_failure": "supervised_deterministic_projection",
    "truncated_quote": "reject_and_archive",
    "unclassified_evidence_failure": "blocked_unclassified",
}


def index_evidence_contracts(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for contract in catalog.get("contracts", []):
        for subtype in contract["causal_subtypes"]:
            if subtype in index:
                raise ValueError(f"duplicate evidence contract for subtype: {subtype}")
            index[subtype] = contract
    return index


def plan_evidence_repair(failure: dict[str, Any], *, mode: str) -> dict[str, Any]:
    if mode not in {"locked_evaluation", "operational"}:
        raise ValueError(f"unsupported evidence repair mode: {mode}")
    subtype = classify_evidence_failure(failure)
    decision = "archive_only" if mode == "locked_evaluation" else OPERATIONAL_DECISIONS[subtype]
    identity = {
        "failure_record_id": failure["record_id"],
        "mode": mode,
        "subtype": subtype,
        "decision": decision,
    }
    return {
        "schema_version": "0.1",
        "record_kind": "evidence_repair_triage",
        "triage_id": stable_id("evidence-triage", identity),
        "failure_record_id": failure["record_id"],
        "failure_signature": failure["failure_signature"],
        "mode": mode,
        "causal_subtype": subtype,
        "decision": decision,
        "new_lineage_required": decision.startswith("supervised_new_lineage"),
        "candidate_output_may_be_semantically_rewritten": False,
        "execution_performed": False,
    }


def bind_evidence_contract(
    plan: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    contracts = index_evidence_contracts(catalog)
    contract = contracts.get(plan["causal_subtype"])
    if contract is None:
        decision = "blocked_missing_contract"
    elif plan["mode"] == "locked_evaluation":
        decision = "archive_only"
    elif contract["execution_policy"] == "blocked":
        decision = "blocked_by_contract"
    else:
        decision = "contract_ready_for_supervised_validation"
    identity = {
        "triage_id": plan["triage_id"],
        "contract_id": contract["contract_id"] if contract else None,
        "decision": decision,
    }
    return {
        "schema_version": "0.1",
        "record_kind": "evidence_repair_contract_binding",
        "binding_id": stable_id("evidence-contract", identity),
        "triage_id": plan["triage_id"],
        "failure_record_id": plan["failure_record_id"],
        "causal_subtype": plan["causal_subtype"],
        "contract_id": contract["contract_id"] if contract else None,
        "decision": decision,
        "required_inputs": contract["required_inputs"] if contract else [],
        "validation_gates": contract["validation_gates"] if contract else [],
        "derived_output": contract["derived_output"] if contract else None,
        "rollback": contract["rollback"] if contract else "preserve parent failure",
        "candidate_output_rewrite_allowed": False,
        "execution_performed": False,
    }
