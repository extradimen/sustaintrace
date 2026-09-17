from __future__ import annotations

import math
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any

from jsonschema import Draft202012Validator

from .v23_preflight import calculation_binding_schema_v23

SUPPORTED_OPERATIONS_V29 = {
    "sum",
    "difference",
    "ratio_per_million",
    "percentage_change",
    "percentage_share",
}


def bind_exact_task_id_schema_v29(
    schema: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Put the frozen task identity in the request schema, never in model output post hoc."""
    if not task_id:
        raise ValueError("v29_task_id_empty")
    bound = deepcopy(schema)
    properties = bound.setdefault("properties", {})
    properties["task_id"] = {"type": "string", "const": task_id}
    required = list(bound.get("required", []))
    if "task_id" not in required:
        required.insert(0, "task_id")
    bound["required"] = required
    Draft202012Validator.check_schema(bound)
    return bound


def calculation_payload_v29(
    model_output: dict[str, Any], expected_task_id: str
) -> dict[str, Any]:
    """Separate a validated identity envelope from calculation bindings."""
    emitted = model_output.get("task_id")
    if emitted != expected_task_id:
        raise ValueError(f"v29_calculation_task_id_mismatch:{emitted}")
    return {key: deepcopy(value) for key, value in model_output.items() if key != "task_id"}


def validate_candidate_preflight_v29(
    tasks: list[dict[str, Any]], plan_registry: dict[str, Any]
) -> dict[str, Any]:
    """Validate the whole frozen task/plan set before the first candidate call."""
    task_ids = [task.get("task_id") for task in tasks]
    if any(not isinstance(task_id, str) or not task_id for task_id in task_ids):
        raise ValueError("v29_task_pack_task_id_invalid")
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("v29_task_pack_task_id_duplicate")
    deterministic = {
        task["task_id"]
        for task in tasks
        if task.get("task_type") == "deterministic_calculation"
    }
    plans = plan_registry.get("plans")
    if not isinstance(plans, dict):
        raise ValueError("v29_calculation_plan_registry_invalid")
    missing = sorted(deterministic - set(plans))
    if missing:
        raise ValueError(f"v29_calculation_plans_missing:{missing}")
    unknown = sorted(set(plans) - set(task_ids))
    if unknown:
        raise ValueError(f"v29_calculation_plans_unknown_tasks:{unknown}")

    checked_operations = []
    for task_id in sorted(deterministic):
        plan = plans[task_id]
        roles = [role.get("role_id") for role in plan.get("roles", [])]
        if not roles or any(not isinstance(role, str) or not role for role in roles):
            raise ValueError(f"v29_calculation_roles_invalid:{task_id}")
        if len(roles) != len(set(roles)):
            raise ValueError(f"v29_calculation_roles_duplicate:{task_id}")
        available = set(roles)
        for step in plan.get("steps", []):
            operation = step.get("operation")
            step_id = step.get("step_id")
            if operation not in SUPPORTED_OPERATIONS_V29:
                raise ValueError(
                    f"v29_calculation_operation_unsupported:{task_id}:{operation}"
                )
            if not isinstance(step_id, str) or not step_id or step_id in available:
                raise ValueError(f"v29_calculation_step_id_invalid:{task_id}:{step_id}")
            inputs = step.get("inputs")
            if not isinstance(inputs, list) or not inputs or not set(inputs) <= available:
                raise ValueError(f"v29_calculation_step_inputs_invalid:{task_id}:{step_id}")
            available.add(step_id)
            checked_operations.append(
                {"task_id": task_id, "step_id": step_id, "operation": operation}
            )
    return {
        "status": "passed",
        "task_count": len(tasks),
        "deterministic_task_count": len(deterministic),
        "plan_count": len(plans),
        "checked_operations": checked_operations,
        "validated_before_candidate_call": True,
    }


def _numeric_tokens(value: str) -> list[float]:
    tokens = re.findall(
        r"[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)", value
    )
    return [float(token.replace(",", "")) for token in tokens]


def _grounded(value: float, evidence: dict[str, Any]) -> bool:
    source = " ".join(
        filter(None, [evidence.get("verbatim_text"), evidence.get("normalized_text")])
    )
    return any(
        math.isclose(value, token, rel_tol=1e-9, abs_tol=1e-9)
        for token in _numeric_tokens(source)
    )


def execute_calculation_plan_v29(
    model_output: dict[str, Any],
    evidence: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Execute the frozen DAG with v2.9 percentage operations and exact grounding."""
    schema = calculation_binding_schema_v23(
        [item["handle"] for item in evidence], plan
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"v29_calculation_binding_schema_failure:{errors[0].message}")
    observations = model_output["observations"]
    evidence_index = {item["handle"]: item for item in evidence}
    values: dict[str, Decimal] = {}
    for role in plan["roles"]:
        role_id = role["role_id"]
        item = observations[role_id]
        expected_unit = role.get("unit")
        if expected_unit and item["unit"].casefold() != expected_unit.casefold():
            raise ValueError(f"v29_calculation_unit_mismatch:{role_id}")
        numeric = float(item["value"])
        if not _grounded(numeric, evidence_index[item["evidence_handle"]]):
            raise ValueError(f"v29_calculation_value_not_grounded:{role_id}")
        values[role_id] = Decimal(str(item["value"]))

    operations = []
    for step in plan.get("steps", []):
        inputs = [values[item] for item in step["inputs"]]
        operation = step["operation"]
        if operation == "sum":
            result = sum(inputs, Decimal("0"))
        elif operation == "difference":
            if len(inputs) != 2:
                raise ValueError(f"v29_difference_arity:{step['step_id']}")
            result = inputs[0] - inputs[1]
        elif operation == "ratio_per_million":
            if len(inputs) != 2 or inputs[1] == 0:
                raise ValueError(f"v29_ratio_inputs_invalid:{step['step_id']}")
            result = inputs[0] * Decimal("1000000") / inputs[1]
        elif operation == "percentage_change":
            if len(inputs) != 2 or inputs[1] == 0:
                raise ValueError(f"v29_percentage_change_inputs_invalid:{step['step_id']}")
            result = (inputs[0] - inputs[1]) * Decimal("100") / inputs[1]
        elif operation == "percentage_share":
            if len(inputs) != 2 or inputs[1] == 0:
                raise ValueError(f"v29_percentage_share_inputs_invalid:{step['step_id']}")
            result = inputs[0] * Decimal("100") / inputs[1]
        else:
            raise ValueError(f"v29_operation_not_registered:{operation}")
        decimals = step.get("rounding_decimals")
        if isinstance(decimals, int):
            result = result.quantize(Decimal("1").scaleb(-decimals))
        values[step["step_id"]] = result
        operations.append(
            {
                "step_id": step["step_id"],
                "operation": operation,
                "inputs": step["inputs"],
                "result": float(result),
            }
        )
    return {
        "status": "passed",
        "framework_owned_operation": True,
        "candidate_selected_operation": False,
        "observations": observations,
        "operations": operations,
        "values": {key: float(value) for key, value in values.items()},
        "numeric_method": "decimal fixed-point from model-bound source literals",
    }
