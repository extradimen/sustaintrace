from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from .v15_grounding import unicode_equivalent_substring


def _numeric_tokens(value: str) -> list[float]:
    tokens = re.findall(
        r"[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
        r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:\.\d+)?(?!,\d)|\d+(?:\.\d+)?)",
        value,
    )
    return [float(re.sub(r"[, \u00a0\u202f]", "", token)) for token in tokens]


def validate_reference_direction_literals_v23(
    contracts: list[dict[str, Any]], bindings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fail before inference when reference magnitude and source sign disagree."""
    contract_index = {item["slot_id"]: item for item in contracts}
    checked = []
    for binding in bindings:
        slot_id = binding["slot_id"]
        contract = contract_index.get(slot_id)
        if contract is None or contract.get("value_type") != "number":
            raise ValueError(f"v23_numeric_contract_missing:{slot_id}")
        reference_value = float(binding["reference_value"])
        tokens = _numeric_tokens(binding["source_literal"])
        comparison = (
            abs(reference_value)
            if contract.get("direction") in {"decrease", "increase"}
            else reference_value
        )
        source_values = (
            [abs(value) for value in tokens]
            if contract.get("direction") in {"decrease", "increase"}
            else tokens
        )
        if not any(
            math.isclose(comparison, value, rel_tol=1e-9, abs_tol=1e-9)
            for value in source_values
        ):
            raise ValueError(f"v23_reference_direction_literal_mismatch:{slot_id}")
        checked.append(
            {
                "slot_id": slot_id,
                "direction": contract.get("direction"),
                "reference_value": reference_value,
                "source_literal": binding["source_literal"],
            }
        )
    return {"status": "passed", "checked_bindings": checked}


def calculation_binding_schema_v23(
    available_handles: list[str], plan: dict[str, Any]
) -> dict[str, Any]:
    """Expose only evidence bindings; operation ownership stays in the frozen plan."""
    if not available_handles:
        raise ValueError("v23_calculation_handles_empty")
    roles = plan.get("roles", [])
    role_ids = [role["role_id"] for role in roles]
    if not role_ids or len(role_ids) != len(set(role_ids)):
        raise ValueError("v23_calculation_roles_invalid")
    observation = {
        "type": "object",
        "required": ["value", "evidence_handle", "period_year", "unit"],
        "properties": {
            "value": {"type": "number"},
            "evidence_handle": {"enum": sorted(available_handles)},
            "period_year": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
            "unit": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["observations"],
        "properties": {
            "observations": {
                "type": "object",
                "required": role_ids,
                "properties": {role_id: observation for role_id in role_ids},
                "additionalProperties": False,
            }
        },
        "additionalProperties": False,
    }
    Draft202012Validator.check_schema(schema)
    return schema


def _grounded(value: float, handle: dict[str, Any]) -> bool:
    text = " ".join(
        filter(None, [handle.get("normalized_text"), handle.get("verbatim_text")])
    )
    return any(
        math.isclose(value, token, rel_tol=1e-9, abs_tol=1e-9)
        for token in _numeric_tokens(text)
    )


def execute_calculation_plan_v23(
    model_output: dict[str, Any],
    evidence: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Execute a frozen calculation DAG after the model binds reported observations."""
    schema = calculation_binding_schema_v23(
        [item["handle"] for item in evidence], plan
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"v23_calculation_binding_schema_failure:{errors[0].message}")
    observations = model_output["observations"]
    evidence_index = {item["handle"]: item for item in evidence}
    values: dict[str, float] = {}
    for role in plan["roles"]:
        role_id = role["role_id"]
        item = observations[role_id]
        if role.get("unit") and item["unit"].casefold() != role["unit"].casefold():
            raise ValueError(f"v23_calculation_unit_mismatch:{role_id}")
        value = float(item["value"])
        if not _grounded(value, evidence_index[item["evidence_handle"]]):
            raise ValueError(f"v23_calculation_value_not_grounded:{role_id}")
        values[role_id] = value
    operations = []
    for step in plan.get("steps", []):
        inputs = [values[item] for item in step["inputs"]]
        operation = step["operation"]
        if operation == "sum":
            result = sum(inputs)
        elif operation == "difference":
            if len(inputs) != 2:
                raise ValueError(f"v23_difference_arity:{step['step_id']}")
            result = inputs[0] - inputs[1]
        elif operation == "ratio_per_million":
            if len(inputs) != 2 or inputs[1] == 0:
                raise ValueError(f"v23_ratio_inputs_invalid:{step['step_id']}")
            result = inputs[0] * 1_000_000 / inputs[1]
        else:
            raise ValueError(f"v23_operation_not_registered:{operation}")
        values[step["step_id"]] = result
        operations.append(
            {
                "step_id": step["step_id"],
                "operation": operation,
                "inputs": step["inputs"],
                "result": result,
            }
        )
    return {
        "status": "passed",
        "framework_owned_operation": True,
        "candidate_selected_operation": False,
        "observations": observations,
        "operations": operations,
        "values": values,
    }


def ground_ordered_string_span_v23(
    *,
    value: str,
    fragments: list[dict[str, str]],
    evidence: list[dict[str, Any]],
    required_terms: list[str] | None = None,
    max_handle_gap: int = 1,
) -> dict[str, Any]:
    """Ground a string over ordered nearby handles without merging source records."""
    if not fragments:
        raise ValueError("v23_string_span_empty")
    handle_order = {item["handle"]: index for index, item in enumerate(evidence)}
    evidence_index = {item["handle"]: item for item in evidence}
    positions = []
    source_fragments = []
    for fragment in fragments:
        handle = fragment["evidence_handle"]
        if handle not in evidence_index:
            raise ValueError(f"v23_string_span_handle_unknown:{handle}")
        verbatim = fragment["verbatim_value"]
        if not unicode_equivalent_substring(
            verbatim, evidence_index[handle]["verbatim_text"]
        ):
            raise ValueError(f"v23_string_span_fragment_not_grounded:{handle}")
        positions.append(handle_order[handle])
        source_fragments.append(verbatim)
    if positions != sorted(set(positions)):
        raise ValueError("v23_string_span_not_strictly_ordered")
    if any(
        right - left > max_handle_gap
        for left, right in zip(positions, positions[1:], strict=False)
    ):
        raise ValueError("v23_string_span_gap_exceeded")
    combined = " ".join(source_fragments)
    if value.casefold() not in combined.casefold():
        raise ValueError("v23_string_value_not_grounded_in_span")
    missing = [
        term
        for term in required_terms or []
        if term.casefold() not in combined.casefold()
    ]
    if missing:
        raise ValueError(f"v23_string_span_required_terms_missing:{missing}")
    return {
        "status": "passed",
        "evidence_handles": [item["evidence_handle"] for item in fragments],
        "source_fragments_preserved": True,
        "required_terms_checked": required_terms or [],
    }
