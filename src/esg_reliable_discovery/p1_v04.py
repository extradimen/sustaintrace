from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

HANDLE_PATTERN = (
    r"^(?:[SI][0-9]{3}-L[0-9]{4}|M[0-9]{3}-B[0-9]{4}|"
    r"M[0-9]{3}-T[0-9]{4}-R[0-9]{4})$"
)


def build_line_evidence_handles(
    source_id: str, page: int, text: str, *, controlled: bool = False
) -> list[dict[str, Any]]:
    prefix = "I" if controlled else "S"
    handles = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        normalized = re.sub(r"\s+", " ", raw_line).strip()
        if normalized:
            handles.append(
                {
                    "handle": f"{prefix}{page:03d}-L{index:04d}",
                    "source_id": source_id,
                    "page": page,
                    "verbatim_text": raw_line.strip(),
                    "normalized_text": normalized,
                }
            )
    return handles


def task_conditioned_schema(
    task_type: str, available_handle_ids: list[str] | None = None
) -> dict[str, Any]:
    handle_schema: dict[str, Any] = {"type": "string", "pattern": HANDLE_PATTERN}
    if available_handle_ids is not None:
        if not available_handle_ids or len(set(available_handle_ids)) != len(
            available_handle_ids
        ):
            raise ValueError("available_handle_ids_must_be_nonempty_and_unique")
        handle_schema = {"type": "string", "enum": available_handle_ids}
    if task_type == "deterministic_calculation":
        calculation_request = {
            "type": ["object", "null"],
            "properties": {
                "operation": {
                    "enum": ["percentage_change", "difference", "sum", "ratio_percent"]
                },
                "inputs": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "required": ["value", "evidence_handle", "role"],
                        "properties": {
                            "value": {"type": "number"},
                            "evidence_handle": handle_schema,
                            "role": {
                                "enum": [
                                    "current", "prior", "numerator", "denominator",
                                    "addend", "minuend", "subtrahend",
                                ]
                            },
                        },
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["operation", "inputs"],
            "additionalProperties": False,
        }
        calculation_properties = {
            "task_id": {"type": "string", "pattern": "^P1-[0-9]{2}-[12]$"},
            "subject": {"type": ["string", "null"]},
            "scope_boundary": {"type": ["string", "null"]},
            "period": {"type": ["string", "null"]},
            "calculation_request": calculation_request,
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "P1 tool-owned deterministic calculation extraction",
            "type": "object",
            "required": list(calculation_properties),
            "properties": calculation_properties,
            "additionalProperties": False,
        }
    properties: dict[str, Any] = {
        "task_id": {"type": "string", "pattern": "^P1-[0-9]{2}-[12]$"},
        "answer_status": {"enum": ["verified_fact", "insufficient_information", "conflict"]},
        "answer": {"type": ["string", "number", "array", "object", "null"]},
        "normalized_value": {"type": ["string", "number", "null"]},
        "normalized_unit": {"type": ["string", "null"]},
        "subject": {"type": ["string", "null"]},
        "scope_boundary": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"]},
        "evidence_handles": {
            "type": "array",
            "items": handle_schema,
            "uniqueItems": True,
        },
    }
    required = list(properties)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"P1 v0.4 {task_type} response",
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }


def resolve_evidence_handles(
    selected: list[str], available: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    index = {item["handle"]: item for item in available}
    if len(index) != len(available):
        raise ValueError("duplicate_available_evidence_handle")
    resolved = []
    for handle in selected:
        if handle not in index:
            raise ValueError(f"unknown_evidence_handle:{handle}")
        item = index[handle]
        resolved.append(
            {
                "source_id": item["source_id"],
                "page": item["page"],
                "verbatim_excerpt": item["verbatim_text"],
                "source_handle": handle,
            }
        )
    return resolved


def execute_registered_calculation(
    request: dict[str, Any], available: list[dict[str, Any]]
) -> dict[str, Any]:
    handle_index = {item["handle"]: item for item in available}
    grounded_inputs = []
    for item in request["inputs"]:
        handle = item["evidence_handle"]
        if handle not in handle_index:
            raise ValueError(f"unknown_calculation_handle:{handle}")
        value = float(item["value"])
        numeric_tokens = [
            float(token.replace(",", ""))
            for token in re.findall(
                r"[-+]?\d[\d,]*(?:\.\d+)?", handle_index[handle]["normalized_text"]
            )
        ]
        grounded = any(
            math.isclose(value, token, rel_tol=1e-9, abs_tol=1e-9)
            for token in numeric_tokens
        )
        if not grounded:
            raise ValueError(f"calculation_value_not_grounded:{handle}")
        grounded_inputs.append({"value": value, "role": item["role"]})
    operation = request["operation"]
    if operation == "percentage_change":
        by_role = {item["role"]: item["value"] for item in grounded_inputs}
        if set(by_role) != {"current", "prior"} or by_role["prior"] == 0:
            raise ValueError("percentage_change_requires_current_and_nonzero_prior")
        values = [by_role["current"], by_role["prior"]]
        result = (values[0] - values[1]) / values[1] * 100
    elif operation == "difference":
        by_role = {item["role"]: item["value"] for item in grounded_inputs}
        if set(by_role) != {"minuend", "subtrahend"}:
            raise ValueError("difference_requires_two_inputs")
        values = [by_role["minuend"], by_role["subtrahend"]]
        result = values[0] - values[1]
    elif operation == "sum":
        if not grounded_inputs or any(item["role"] != "addend" for item in grounded_inputs):
            raise ValueError("sum_requires_addends")
        values = [item["value"] for item in grounded_inputs]
        result = sum(values)
    elif operation == "ratio_percent":
        by_role = {item["role"]: item["value"] for item in grounded_inputs}
        if set(by_role) != {"numerator", "denominator"} or by_role["denominator"] == 0:
            raise ValueError("ratio_percent_requires_numerator_and_nonzero_denominator")
        values = [by_role["numerator"], by_role["denominator"]]
        result = values[0] / values[1] * 100
    else:
        raise ValueError(f"unregistered_operation:{operation}")
    return {
        "operation": operation,
        "inputs": values,
        "result": result,
        "executed_by": "deterministic_framework",
        "model_result_used": False,
    }


def finalize_v04_output(
    model_output: Any, task_type: str, available_handles: list[dict[str, Any]]
) -> dict[str, Any]:
    """Validate and enrich without modifying or repairing the model-authored object."""
    schema = task_conditioned_schema(task_type)
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if schema_errors:
        raise ValueError(f"task_conditioned_schema_failure:{schema_errors[0].message}")
    deterministic_calculation = None
    if task_type == "deterministic_calculation":
        request = model_output["calculation_request"]
        selected_handles = (
            list(dict.fromkeys(item["evidence_handle"] for item in request["inputs"]))
            if request is not None
            else []
        )
        resolved = resolve_evidence_handles(selected_handles, available_handles)
        if request is not None:
            deterministic_calculation = execute_registered_calculation(
                request, available_handles
            )
            value = deterministic_calculation["result"]
            deterministic_calculation["direction"] = (
                "increase" if value > 0 else "decrease" if value < 0 else "no_change"
            )
    else:
        resolved = resolve_evidence_handles(
            model_output["evidence_handles"], available_handles
        )
    return {
        "model_output": model_output,
        "resolved_evidence": resolved,
        "deterministic_calculation": deterministic_calculation,
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }
