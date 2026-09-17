from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal
from typing import Any

from .v15_grounding import unicode_equivalent_substring
from .v23_preflight import execute_calculation_plan_v23
from .v24_integrity import normalize_calculation_binding_v24


def _canonical_calculation_unit(value: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", value.casefold())
    if key in {"1000tco2e", "thousandtco2e", "ktco2e"}:
        return "thousand_tCO2e"
    return value


def normalize_calculation_binding_v25(
    model_output: dict[str, Any], plan: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Accept a scalar comparison plus its separately emitted evidence handle."""
    prepared = deepcopy(model_output)
    request = prepared.get("calculation_request")
    scalar_comparison_adapted = False
    if isinstance(request, dict) and isinstance(
        request.get("comparison_value"), (int, float)
    ):
        handle = request.get("comparison_evidence_handle")
        if not isinstance(handle, str) or not handle:
            raise ValueError("v25_calculation_comparison_handle_missing")
        request["comparison_value"] = {
            "value": request["comparison_value"],
            "evidence_handle": handle,
            "period_year": request.get("comparison_period_year", "2025"),
            "unit": request.get("unit", ""),
        }
        scalar_comparison_adapted = True
    binding, audit = normalize_calculation_binding_v24(prepared, plan)
    unit_adaptations = []
    plan_units = {role["role_id"]: role.get("unit") for role in plan.get("roles", [])}
    for role_id, observation in binding["observations"].items():
        canonical = _canonical_calculation_unit(str(observation.get("unit", "")))
        expected = plan_units.get(role_id)
        if expected and canonical.casefold() == str(expected).casefold():
            if observation.get("unit") != expected:
                unit_adaptations.append(
                    {"role_id": role_id, "source_unit": observation.get("unit")}
                )
            observation["unit"] = expected
    return binding, {
        **audit,
        "v25_scalar_comparison_with_separate_handle_adapted": (
            scalar_comparison_adapted
        ),
        "candidate_comparison_value_modified": False,
        "deterministic_unit_alias_adaptations": unit_adaptations,
    }


def select_single_block_ordered_spans_v25(
    contracts: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use a scalar grounded string when one block contains every required term."""
    selected = deepcopy(contracts)
    lowered: list[dict[str, Any]] = []
    for contract in selected:
        if contract.get("string_input_shape") != "ordered_span":
            continue
        terms = contract.get("required_value_terms", [])
        matching_handles = []
        for item in evidence:
            source = item["verbatim_text"]
            if all(unicode_equivalent_substring(term, source) for term in terms):
                matching_handles.append(item["handle"])
        if matching_handles:
            contract.pop("string_input_shape", None)
            contract.pop("max_handle_gap", None)
            lowered.append(
                {
                    "slot_id": contract["slot_id"],
                    "eligible_handles": matching_handles,
                    "reason": "all required terms occur in one evidence block",
                }
            )
    return selected, {
        "single_block_ordered_span_slots": lowered,
        "candidate_semantics_modified": False,
        "required_terms_modified": False,
    }


def execute_calculation_plan_v25(
    model_output: dict[str, Any],
    evidence: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Preserve v2.3 validation while executing the frozen DAG in decimal arithmetic."""
    result = execute_calculation_plan_v23(model_output, evidence, plan)
    values = {
        role["role_id"]: Decimal(str(model_output["observations"][role["role_id"]]["value"]))
        for role in plan["roles"]
    }
    operations = []
    for step in plan.get("steps", []):
        inputs = [values[item] for item in step["inputs"]]
        if step["operation"] == "sum":
            computed = sum(inputs, Decimal("0"))
        elif step["operation"] == "difference":
            computed = inputs[0] - inputs[1]
        elif step["operation"] == "ratio_per_million":
            computed = inputs[0] * Decimal("1000000") / inputs[1]
        else:
            raise ValueError(f"v25_operation_not_registered:{step['operation']}")
        values[step["step_id"]] = computed
        operations.append(
            {
                "step_id": step["step_id"],
                "operation": step["operation"],
                "inputs": step["inputs"],
                "result": float(computed),
            }
        )
    result["operations"] = operations
    result["values"] = {key: float(value) for key, value in values.items()}
    result["numeric_method"] = "decimal fixed-point from model-bound source literals"
    return result
