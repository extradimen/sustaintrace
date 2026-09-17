from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from .p1_v04 import (
    execute_registered_calculation,
    finalize_v04_output,
    resolve_evidence_handles,
)


def _handle_schema(available_handle_ids: list[str]) -> dict[str, Any]:
    if not available_handle_ids or len(set(available_handle_ids)) != len(
        available_handle_ids
    ):
        raise ValueError("available_handle_ids_must_be_nonempty_and_unique")
    return {"type": "string", "enum": available_handle_ids}


def _calculation_input(handle: dict[str, Any], roles: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["value", "evidence_handle", "role"],
        "properties": {
            "value": {"type": "number"},
            "evidence_handle": handle,
            "role": {"enum": roles},
        },
        "additionalProperties": False,
    }


def _binary_operation(
    operation: str, handle: dict[str, Any], roles: tuple[str, str]
) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["operation", "inputs"],
        "properties": {
            "operation": {"const": operation},
            "inputs": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "items": _calculation_input(handle, list(roles)),
                "allOf": [
                    {
                        "contains": {"properties": {"role": {"const": role}}},
                        "minContains": 1,
                        "maxContains": 1,
                    }
                    for role in roles
                ],
            },
        },
        "additionalProperties": False,
    }


def _calculation_schema_v073(available_handle_ids: list[str]) -> dict[str, Any]:
    handle = _handle_schema(available_handle_ids)
    period_observation = {
        "type": "object",
        "required": ["value", "evidence_handle", "period_year"],
        "properties": {
            "value": {"type": "number"},
            "evidence_handle": handle,
            "period_year": {
                "anyOf": [
                    {"type": "integer", "minimum": 1900, "maximum": 2200},
                    {"type": "string", "pattern": r"^(?:FY)?(?:19|20)?\d{2}$"},
                ]
            },
        },
        "additionalProperties": False,
    }
    percentage_change = {
        "type": "object",
        "required": ["operation", "inputs"],
        "properties": {
            "operation": {"const": "percentage_change"},
            "inputs": {
                "type": "array", "minItems": 2, "maxItems": 2,
                "items": period_observation,
            },
        },
        "additionalProperties": False,
    }
    request = {
        "anyOf": [
            {"type": "null"},
            {
                "oneOf": [
                    percentage_change,
                    _binary_operation(
                        "ratio_percent", handle, ("numerator", "denominator")
                    ),
                    _binary_operation(
                        "difference", handle, ("minuend", "subtrahend")
                    ),
                    {
                        "type": "object",
                        "required": ["operation", "inputs"],
                        "properties": {
                            "operation": {"const": "sum"},
                            "inputs": {
                                "type": "array",
                                "minItems": 2,
                                "items": _calculation_input(handle, ["addend"]),
                            },
                        },
                        "additionalProperties": False,
                    },
                ]
            },
        ]
    }
    properties = {"calculation_request": request}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "P1 v0.7.3 operation-conditioned calculation",
        "type": "object",
        "required": list(properties),
        "properties": properties,
        "additionalProperties": False,
    }


def task_conditioned_schema_v07(
    task_type: str, available_handle_ids: list[str]
) -> dict[str, Any]:
    if task_type == "deterministic_calculation":
        return _calculation_schema_v073(available_handle_ids)
    handle = _handle_schema(available_handle_ids)
    if task_type == "abstention":
        properties = {
            "answer": {"type": "null"},
            "normalized_value": {"type": "null"},
            "evidence_handles": {"type": "array", "maxItems": 0},
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "P1 v0.7.1 minimal abstention",
            "type": "object",
            "required": list(properties),
            "properties": properties,
            "additionalProperties": False,
        }
    if task_type in {
        "cross_page_relation",
        "scope_subject_boundary",
        "source_conflict",
        "direct_extraction",
    }:
        properties = {
            "answer": {"type": ["string", "number", "array", "object"]},
            "evidence_handles": {
                "type": "array", "minItems": 1, "items": handle,
                "uniqueItems": True,
            },
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": f"P1 v0.7.5 minimal relational answer: {task_type}",
            "type": "object",
            "required": list(properties),
            "properties": properties,
            "additionalProperties": False,
        }
    metadata = {
        "task_id": {"type": "string", "pattern": "^P1-[0-9]{2}-[12]$"},
        "subject": {"type": ["string", "null"]},
        "scope_boundary": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"]},
    }
    if task_type == "controlled_conflict":
        properties = {
            "source_claims": {
                "type": "array",
                "minItems": 2,
                "items": {
                    "type": "object",
                    "required": [
                        "source_id", "evidence_handle", "normalized_value",
                        "normalized_unit",
                    ],
                    "properties": {
                        "source_id": {"type": "string"},
                        "evidence_handle": handle,
                        "normalized_value": {"type": ["number", "string"]},
                        "normalized_unit": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "P1 v0.7 grounded source claims",
            "type": "object",
            "required": list(properties),
            "properties": properties,
            "additionalProperties": False,
        }
    properties = {
        **metadata,
        "answer": {"type": ["string", "number", "array", "object", "null"]},
        "normalized_value": {"type": ["string", "number", "null"]},
        "normalized_unit": {"type": ["string", "null"]},
        "evidence_handles": {
            "type": "array", "items": handle, "uniqueItems": True,
        },
    }
    supported = {
        "properties": {
            "answer": {"not": {"type": "null"}},
            "evidence_handles": {"minItems": 1},
        }
    }
    absent = {
        "properties": {
            "answer": {"type": "null"},
            "normalized_value": {"type": "null"},
            "evidence_handles": {"maxItems": 0},
        }
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"P1 v0.7 {task_type} evidence state",
        "type": "object",
        "required": list(properties),
        "properties": properties,
        "oneOf": [supported, absent],
        "additionalProperties": False,
    }


def _numeric_claim_grounded(value: float, text: str) -> bool:
    tokens = [
        float(token.replace(",", ""))
        for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    ]
    return any(math.isclose(value, token, rel_tol=1e-9, abs_tol=1e-9) for token in tokens)


def _claim_key(value: str | float) -> tuple[str, str | float]:
    if isinstance(value, (int, float)):
        return ("number", float(value))
    return ("text", " ".join(value.casefold().split()))


def normalize_period_year(value: int | str) -> tuple[int, int | str]:
    """Normalize controlled fiscal-year literals while retaining the model literal."""
    if isinstance(value, bool):
        raise ValueError("period_year_boolean_invalid")
    if isinstance(value, int):
        year = value
    elif isinstance(value, str):
        literal = value.strip().upper()
        digits = literal[2:] if literal.startswith("FY") else literal
        if not digits.isdigit() or len(digits) not in {2, 4}:
            raise ValueError(f"period_year_literal_invalid:{value}")
        year = int(digits)
        if len(digits) == 2:
            year += 2000 if year <= 49 else 1900
    else:
        raise ValueError(f"period_year_type_invalid:{type(value).__name__}")
    if not 1900 <= year <= 2200:
        raise ValueError(f"period_year_out_of_range:{year}")
    return year, value


def finalize_v07_output(
    model_output: Any, task_type: str, available_handles: list[dict[str, Any]]
) -> dict[str, Any]:
    if task_type == "deterministic_calculation":
        schema = task_conditioned_schema_v07(
            task_type, [item["handle"] for item in available_handles]
        )
        errors = sorted(
            Draft202012Validator(schema).iter_errors(model_output),
            key=lambda error: list(error.path),
        )
        if errors:
            raise ValueError(f"v074_schema_failure:{errors[0].message}")
        request = model_output["calculation_request"]
        if request is not None and request["operation"] == "percentage_change":
            normalized_inputs = []
            for item in request["inputs"]:
                year, literal = normalize_period_year(item["period_year"])
                normalized_inputs.append(
                    {**item, "period_year": year, "model_period_literal": literal}
                )
            years = [item["period_year"] for item in normalized_inputs]
            if len(set(years)) != 2:
                raise ValueError("percentage_change_requires_two_distinct_period_years")
            handle_index = {item["handle"]: item for item in available_handles}
            for item in normalized_inputs:
                evidence = handle_index[item["evidence_handle"]]
                period_text = " ".join(
                    filter(None, [
                        evidence.get("normalized_text"),
                        evidence.get("table_header_context"),
                        evidence.get("period_header_context"),
                    ])
                )
                literal = str(item["model_period_literal"])
                if (
                    literal not in period_text
                    and str(item["period_year"]) not in period_text
                ):
                    raise ValueError(
                        f"calculation_period_not_grounded:{item['evidence_handle']}"
                    )
            latest = max(years)
            transformed_request = {
                "operation": "percentage_change",
                "inputs": [
                    {
                        "value": item["value"],
                        "evidence_handle": item["evidence_handle"],
                        "role": "current" if item["period_year"] == latest else "prior",
                    }
                    for item in normalized_inputs
                ],
            }
            calculation = execute_registered_calculation(
                transformed_request, available_handles
            )
            value = calculation["result"]
            calculation["direction"] = (
                "increase" if value > 0 else "decrease" if value < 0 else "no_change"
            )
            selected = list(dict.fromkeys(
                item["evidence_handle"] for item in request["inputs"]
            ))
            return {
                "model_output": model_output,
                "resolved_evidence": resolve_evidence_handles(
                    selected, available_handles
                ),
                "framework_period_role_assignment": {
                    "current_year": latest,
                    "prior_year": min(years),
                    "model_period_literals": [
                        item["model_period_literal"] for item in normalized_inputs
                    ],
                    "normalization_rule": "controlled_FY_or_calendar_year_literal",
                },
                "deterministic_calculation": calculation,
                "framework_evidence_state": "supported",
                "model_output_modified": False,
                "posthoc_semantic_repair_applied": False,
            }
        result = finalize_v04_output(model_output, task_type, available_handles)
        result["framework_evidence_state"] = (
            "supported" if model_output["calculation_request"] is not None else "absent"
        )
        return result
    schema = task_conditioned_schema_v07(
        task_type, [item["handle"] for item in available_handles]
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"v07_schema_failure:{errors[0].message}")
    if task_type != "controlled_conflict":
        resolved = resolve_evidence_handles(
            model_output["evidence_handles"], available_handles
        )
        return {
            "model_output": model_output,
            "resolved_evidence": resolved,
            "framework_evidence_state": "supported" if resolved else "absent",
            "deterministic_calculation": None,
            "model_output_modified": False,
            "posthoc_semantic_repair_applied": False,
        }
    index = {item["handle"]: item for item in available_handles}
    selected: list[str] = []
    claim_values = []
    grounded_claims = []
    for claim in model_output["source_claims"]:
        handle = claim["evidence_handle"]
        evidence = index[handle]
        if claim["source_id"] != evidence["source_id"]:
            raise ValueError(f"claim_source_mismatch:{handle}")
        value = claim["normalized_value"]
        if isinstance(value, (int, float)) and not _numeric_claim_grounded(
            float(value), evidence["normalized_text"]
        ):
            raise ValueError(f"claim_value_not_grounded:{handle}")
        selected.append(handle)
        claim_values.append(_claim_key(value))
        grounded_claims.append({**claim, "grounded": True})
    distinct_sources = {claim["source_id"] for claim in grounded_claims}
    state = (
        "contradictory_sources"
        if len(distinct_sources) >= 2 and len(set(claim_values)) >= 2
        else "consistent_sources"
    )
    return {
        "model_output": model_output,
        "grounded_source_claims": grounded_claims,
        "resolved_evidence": resolve_evidence_handles(
            list(dict.fromkeys(selected)), available_handles
        ),
        "framework_evidence_state": state,
        "deterministic_calculation": None,
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }
