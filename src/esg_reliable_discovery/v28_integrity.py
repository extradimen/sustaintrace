from __future__ import annotations

import re
import unicodedata
from typing import Any

from .v26_integrity import validate_candidate_handles_v26


def validate_stage_a_task_id_v28(
    model_output: dict[str, Any], expected_task_id: str
) -> dict[str, Any]:
    """Fail explicitly on a missing/wrong task id; never synthesize the field."""
    emitted = model_output.get("task_id")
    if emitted is None:
        raise ValueError("v28_stage_a_task_id_missing")
    if emitted != expected_task_id:
        raise ValueError(f"v28_stage_a_task_id_mismatch:{emitted}")
    return {
        "status": "passed",
        "expected_task_id": expected_task_id,
        "emitted_task_id": emitted,
        "task_id_synthesized": False,
    }


def bind_handle_role_calculation_request_v28(
    model_output: dict[str, Any],
    plan: dict[str, Any],
    available_handles: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind unlabeled inputs only through an exact frozen handle-to-role map."""
    handle_audit = validate_candidate_handles_v26(model_output, available_handles)
    request = model_output.get("calculation_request")
    if not isinstance(request, dict):
        raise ValueError("v28_calculation_request_missing")
    inputs = request.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("v28_calculation_inputs_missing")
    role_map = plan.get("candidate_handle_role_map")
    if not isinstance(role_map, dict) or not role_map:
        raise ValueError("v28_frozen_handle_role_map_missing")
    plan_roles = [item["role_id"] for item in plan.get("roles", [])]
    if set(role_map.values()) - set(plan_roles):
        raise ValueError("v28_frozen_handle_role_map_unknown_role")

    observations: dict[str, dict[str, Any]] = {}
    source_literals = []
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("v28_calculation_input_invalid")
        handle = item.get("evidence_handle")
        role_id = role_map.get(handle)
        if role_id is None:
            raise ValueError(f"v28_unmapped_calculation_handle:{handle}")
        if role_id in observations:
            raise ValueError(f"v28_calculation_role_duplicate:{role_id}")
        observations[role_id] = {
            "value": item["value"],
            "period_year": item["period_year"],
            "evidence_handle": handle,
            "unit": item.get("unit") or request.get("unit") or plan_roles_unit(plan, role_id),
        }
        source_literals.append(
            {
                "role_id": role_id,
                "evidence_handle": handle,
                "candidate_metric": item.get("metric"),
                "candidate_value": item["value"],
                "candidate_period_year": item["period_year"],
            }
        )
    missing = [role_id for role_id in plan_roles if role_id not in observations]
    return {"observations": observations}, {
        "status": "passed" if not missing else "partially_supported",
        "source_shape": "exact_frozen_handle_role_binding",
        "bound_roles": list(observations),
        "missing_roles": missing,
        "candidate_output_complete": not missing,
        "candidate_source_literals": source_literals,
        "v26_handle_audit": handle_audit,
        "candidate_semantics_modified": False,
        "posthoc_value_invention": False,
        "approximate_handle_repair": False,
        "framework_operation_remains_frozen": True,
    }


def plan_roles_unit(plan: dict[str, Any], role_id: str) -> str:
    return next(item["unit"] for item in plan["roles"] if item["role_id"] == role_id)


def compare_text_slot_v28(candidate: str, reference: str) -> dict[str, Any]:
    """Report literal and semantic-normalized comparisons as distinct dimensions."""

    def normalized(value: str) -> str:
        value = unicodedata.normalize("NFKC", value).casefold()
        value = value.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
        return " ".join(re.findall(r"[a-z0-9]+", value))

    left = normalized(candidate)
    right = normalized(reference)
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    union = left_tokens | right_tokens
    return {
        "literal_exact": candidate == reference,
        "normalized_exact": left == right,
        "token_jaccard": len(left_tokens & right_tokens) / len(union) if union else 1.0,
        "candidate_original": candidate,
        "reference_original": reference,
        "semantic_rewrite_applied": False,
    }
