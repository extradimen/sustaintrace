from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any


def evidence_handle_model_schema(model_schema: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(model_schema)
    schema["$defs"]["evidence"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_handle", "location", "excerpt", "evidence_strength"],
        "properties": {
            "source_handle": {"type": "string", "pattern": "^[SI][0-9]{3}$"},
            "location": {"type": "string", "minLength": 1},
            "excerpt": {"type": "string", "minLength": 1, "maxLength": 500},
            "evidence_strength": {"enum": ["direct", "indirect", "context"]},
            "printed_page": {"type": ["string", "null"]},
            "transformation": {"type": ["string", "null"]},
        },
    }
    schema["title"] = f"{schema.get('title', 'ESG Finding Content')} with Evidence Handles"
    return schema


def resolve_evidence_handles(model_output: Any, context_manifest: dict[str, Any]) -> Any:
    handle_map = {
        item["source_handle"]: item for item in context_manifest.get("evidence_handles", [])
    }
    cards = model_output if isinstance(model_output, list) else [model_output]
    resolved_cards = []
    for source_card in cards:
        if not isinstance(source_card, dict):
            resolved_cards.append(source_card)
            continue
        card = deepcopy(source_card)
        for evidence_kind in ("supporting_evidence", "contrary_evidence"):
            resolved_items = []
            for evidence in card.get(evidence_kind, []):
                item = deepcopy(evidence)
                handle = item.pop("source_handle", None)
                if handle not in handle_map:
                    raise ValueError(f"unknown_evidence_handle:{handle}")
                source = handle_map[handle]
                item.update(
                    {
                        "document_id": source["document_id"],
                        "document_sha256": source["document_sha256"],
                        "page": source["page"],
                    }
                )
                resolved_items.append(item)
            card[evidence_kind] = resolved_items
        resolved_cards.append(card)
    return resolved_cards if isinstance(model_output, list) else resolved_cards[0]


def _last_number(value: str) -> float:
    matches = re.findall(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    if not matches:
        raise ValueError(f"no_numeric_input:{value}")
    return float(matches[-1])


def verify_deterministic_calculation(
    card: dict[str, Any], operation: str
) -> dict[str, Any]:
    calculation = card.get("calculation") or {}
    inputs = calculation.get("inputs") or []
    result = {
        "operation": operation,
        "model_result": calculation.get("result"),
        "model_unit": calculation.get("unit"),
        "parsed_inputs": [],
        "tool_result": None,
        "consistent": False,
        "error": None,
        "model_output_modified": False,
    }
    try:
        values = [_last_number(str(value)) for value in inputs]
        result["parsed_inputs"] = values
        if operation == "percent_change_current_prior":
            if len(values) != 2:
                raise ValueError("percent_change_requires_exactly_two_inputs")
            if values[1] == 0:
                raise ValueError("prior_value_is_zero")
            tool_result = (values[0] - values[1]) / values[1] * 100
        else:
            raise ValueError(f"unsupported_operation:{operation}")
        result["tool_result"] = tool_result
        result["consistent"] = math.isclose(
            float(calculation["result"]), tool_result, rel_tol=1e-6, abs_tol=1e-6
        )
    except (KeyError, TypeError, ValueError) as error:
        result["error"] = str(error)
    return result
