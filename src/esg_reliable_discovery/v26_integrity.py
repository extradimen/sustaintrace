from __future__ import annotations

from copy import deepcopy
from typing import Any

from .v13_atomic_projection import validate_and_project_slots
from .v15_grounding import unicode_equivalent_substring
from .v25_integrity import normalize_calculation_binding_v25


def _candidate_handles(model_output: dict[str, Any]) -> list[str]:
    if isinstance(model_output.get("evidence_handles"), list):
        return [str(item) for item in model_output["evidence_handles"]]
    if isinstance(model_output.get("observations"), dict):
        return [
            item.get("evidence_handle", "")
            for item in model_output["observations"].values()
            if isinstance(item, dict)
        ]
    request = model_output.get("calculation_request", {})
    handles = [
        item.get("evidence_handle", "")
        for item in request.get("inputs", [])
        if isinstance(item, dict)
    ]
    comparison = request.get("comparison_value")
    if isinstance(comparison, dict):
        handles.append(comparison.get("evidence_handle", ""))
    elif request.get("comparison_evidence_handle"):
        handles.append(request["comparison_evidence_handle"])
    return handles


def validate_candidate_handles_v26(
    model_output: dict[str, Any], available_handles: list[str]
) -> dict[str, Any]:
    """Fail with a compact audit before schema projection on invented handles."""
    allowed = set(available_handles)
    emitted = _candidate_handles(model_output)
    invalid = sorted({handle for handle in emitted if handle not in allowed})
    if invalid:
        raise ValueError(f"v26_candidate_evidence_handles_invalid:{invalid}")
    return {
        "status": "passed",
        "emitted_handle_count": len(emitted),
        "unique_emitted_handle_count": len(set(emitted)),
        "invalid_handles": [],
    }


def normalize_calculation_binding_v26(
    model_output: dict[str, Any],
    plan: dict[str, Any],
    available_handles: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind unlabeled ordered inputs only when the frozen plan owns their order."""
    handle_audit = validate_candidate_handles_v26(model_output, available_handles)
    try:
        binding, audit = normalize_calculation_binding_v25(model_output, plan)
        return binding, {**audit, "v26_handle_audit": handle_audit}
    except ValueError as error:
        if not str(error).startswith("v24_calculation_metric_unmatched:"):
            raise
    request = model_output.get("calculation_request")
    role_order = plan.get("candidate_input_role_order")
    inputs = request.get("inputs", []) if isinstance(request, dict) else []
    plan_roles = [role["role_id"] for role in plan.get("roles", [])]
    if not isinstance(role_order, list) or role_order != plan_roles:
        raise ValueError("v26_unlabeled_calculation_role_order_not_frozen")
    if len(inputs) != len(role_order) or any(item.get("metric") for item in inputs):
        raise ValueError("v26_unlabeled_calculation_inputs_not_exact_ordered_shape")
    unit = str(request.get("unit") or plan.get("candidate_input_unit") or "")
    if not unit:
        raise ValueError("v26_unlabeled_calculation_unit_not_frozen")
    observations = {
        role_id: {
            "value": item["value"],
            "evidence_handle": item["evidence_handle"],
            "period_year": item["period_year"],
            "unit": unit,
        }
        for role_id, item in zip(role_order, inputs, strict=True)
    }
    return {"observations": observations}, {
        "adapter_applied": True,
        "source_shape": "unlabeled_ordered_calculation_inputs",
        "v26_frozen_role_order_applied": role_order,
        "v26_handle_audit": handle_audit,
        "candidate_operation_fields_ignored": [
            key for key in ("operation", "calculated_sum", "difference") if key in request
        ],
        "candidate_semantics_modified": False,
        "framework_operation_remains_frozen": True,
    }


def select_semantic_single_block_spans_v26(
    contracts: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Lower ordered spans using frozen groups of literal alternatives."""
    selected = deepcopy(contracts)
    lowered = []
    for contract in selected:
        groups = contract.get("required_term_groups", [])
        if contract.get("string_input_shape") != "ordered_span" or not groups:
            continue
        for item in evidence:
            text = item["verbatim_text"]
            matches = [
                next(
                    (
                        term
                        for term in group
                        if unicode_equivalent_substring(term.casefold(), text.casefold())
                    ),
                    None,
                )
                for group in groups
            ]
            if all(matches):
                contract.pop("string_input_shape", None)
                contract.pop("max_handle_gap", None)
                contract.pop("required_value_terms", None)
                contract["required_value_terms"] = matches
                contract["claim_value_source"] = "candidate_selected_verbatim"
                lowered.append(
                    {
                        "slot_id": contract["slot_id"],
                        "evidence_handle": item["handle"],
                        "matched_terms": matches,
                    }
                )
                break
    return selected, {
        "semantic_single_block_slots": lowered,
        "term_groups_frozen_before_candidate": True,
        "candidate_semantics_modified": False,
    }


def project_atomic_slots_v26(
    *,
    model_output: dict[str, Any],
    evidence: list[dict[str, Any]],
    required_slots: list[dict[str, Any]],
    framework_subject: dict[str, str],
) -> dict[str, Any]:
    """Credit valid emitted atoms and explicitly preserve missing-slot state."""
    emitted = model_output.get("slots")
    if not isinstance(emitted, list):
        raise ValueError("v26_slots_not_array")
    contract_index = {item["slot_id"]: item for item in required_slots}
    emitted_ids = [item.get("slot_id") for item in emitted if isinstance(item, dict)]
    if len(emitted_ids) != len(emitted) or len(set(emitted_ids)) != len(emitted_ids):
        raise ValueError("v26_slot_ids_invalid_or_duplicate")
    unknown = sorted(set(emitted_ids) - set(contract_index))
    if unknown:
        raise ValueError(f"v26_unknown_slots:{unknown}")
    claims = []
    for item in emitted:
        contract = deepcopy(contract_index[item["slot_id"]])
        candidate_item = deepcopy(item)
        if contract.get("claim_value_source") == "candidate_selected_verbatim":
            candidate_item["value"] = candidate_item["verbatim_value"]
        projected = validate_and_project_slots(
            model_output={"slots": [candidate_item]},
            evidence=evidence,
            required_slots=[contract],
            framework_subject=framework_subject,
        )
        claim = projected["validated_claims"][0]
        claim["claim_id"] = f"CLAIM-{len(claims) + 1:04d}"
        claim["model_emitted_value"] = item["value"]
        claims.append(claim)
    missing = [item["slot_id"] for item in required_slots if item["slot_id"] not in emitted_ids]
    return {
        "validated_claims": claims,
        "evidence_state": "supported" if not missing else "partially_supported",
        "missing_required_slots": missing,
        "missing_values_invented": False,
        "source_verbatim_preserved": True,
        "candidate_semantics_modified": False,
    }
