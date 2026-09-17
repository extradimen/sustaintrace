from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from .p1_v04 import execute_registered_calculation, resolve_evidence_handles


def calculation_schema_v21(available_handles: list[str]) -> dict[str, Any]:
    handle = {"type": "string", "enum": available_handles}
    observation = {
        "type": "object",
        "required": ["value", "evidence_handle", "metric", "period_year", "unit"],
        "properties": {
            "value": {"type": "number"},
            "evidence_handle": handle,
            "metric": {"type": "string", "minLength": 1},
            "period_year": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
            "unit": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    request = {
        "type": "object",
        "required": ["operation", "inputs", "comparison_value"],
        "properties": {
            "operation": {"const": "sum"},
            "inputs": {"type": "array", "minItems": 2, "items": observation},
            "comparison_value": observation,
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["calculation_request"],
        "properties": {"calculation_request": request},
        "additionalProperties": False,
    }


def _grounded(value: float, handle: dict[str, Any]) -> bool:
    text = " ".join(filter(None, [handle.get("normalized_text"), handle.get("verbatim_text")]))
    tokens = [
        float(token.replace(",", "")) for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    ]
    return any(math.isclose(value, token, rel_tol=1e-9, abs_tol=1e-9) for token in tokens)


def finalize_calculation_v21(
    model_output: dict[str, Any], available_handles: list[dict[str, Any]]
) -> dict[str, Any]:
    schema = calculation_schema_v21([item["handle"] for item in available_handles])
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output), key=lambda e: list(e.path)
    )
    if errors:
        raise ValueError(f"v21_calculation_schema_failure:{errors[0].message}")
    request = model_output["calculation_request"]
    comparison = request["comparison_value"]
    periods = {str(item["period_year"]) for item in [*request["inputs"], comparison]}
    units = {item["unit"].casefold() for item in [*request["inputs"], comparison]}
    if len(periods) != 1:
        raise ValueError("v21_calculation_period_mismatch")
    if len(units) != 1:
        raise ValueError("v21_calculation_unit_mismatch")
    index = {item["handle"]: item for item in available_handles}
    for item in [*request["inputs"], comparison]:
        if not _grounded(float(item["value"]), index[item["evidence_handle"]]):
            raise ValueError(f"v21_calculation_value_not_grounded:{item['evidence_handle']}")
    executable = {
        "operation": "sum",
        "inputs": [
            {"value": item["value"], "evidence_handle": item["evidence_handle"], "role": "addend"}
            for item in request["inputs"]
        ],
    }
    calculation = execute_registered_calculation(executable, available_handles)
    disclosed = float(comparison["value"])
    calculation["issuer_disclosed_value"] = disclosed
    calculation["recomputed_minus_disclosed"] = calculation["result"] - disclosed
    selected = list(
        dict.fromkeys(item["evidence_handle"] for item in [*request["inputs"], comparison])
    )
    return {
        "model_output": model_output,
        "resolved_evidence": resolve_evidence_handles(selected, available_handles),
        "deterministic_calculation": calculation,
        "framework_evidence_state": "supported",
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }
