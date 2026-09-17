from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from .p1_v04 import resolve_evidence_handles


def direct_extraction_schema_v12(available_handles: list[str]) -> dict[str, Any]:
    properties = {
        "answer": {"type": ["string", "number", "array", "object"]},
        "evidence_handles": {
            "type": "array",
            "minItems": 1,
            "items": {"enum": available_handles},
            "uniqueItems": True,
        },
        "normalized_value": {"type": ["number", "string"]},
        "normalized_unit": {"type": "string", "minLength": 1},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["answer", "evidence_handles"],
        "properties": properties,
        "additionalProperties": False,
    }


def finalize_direct_v12(
    model_output: Any, available_handles: list[dict[str, Any]], question: str
) -> dict[str, Any]:
    schema = direct_extraction_schema_v12([item["handle"] for item in available_handles])
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"v12_direct_schema_failure:{errors[0].message}")
    resolved = resolve_evidence_handles(model_output["evidence_handles"], available_handles)
    evidence_text = " ".join(item["verbatim_excerpt"] for item in resolved)
    value = model_output.get("normalized_value")
    if isinstance(value, (int, float)):
        tokens = [
            float(token.replace(",", ""))
            for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", evidence_text)
        ]
        if not any(math.isclose(float(value), token, rel_tol=1e-9) for token in tokens):
            raise ValueError("v12_normalized_value_not_grounded")
    unit = model_output.get("normalized_unit")
    if unit is not None:
        grounding = f"{question} {evidence_text}".casefold()
        normalized_unit = " ".join(unit.casefold().split())
        if normalized_unit not in " ".join(grounding.split()):
            raise ValueError("v12_normalized_unit_not_grounded")
    return {
        "model_output": model_output,
        "resolved_evidence": resolved,
        "framework_evidence_state": "supported",
        "deterministic_calculation": None,
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
        "optional_normalization_validated": value is not None or unit is not None,
    }
