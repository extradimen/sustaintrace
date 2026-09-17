from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .v13_atomic_projection import validate_and_project_slots
from .v15_grounding import unicode_equivalent_substring


def flatten_object_contracts(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lower declared object fields to candidate-visible atomic scalar slots."""
    flattened: list[dict[str, Any]] = []
    for contract in contracts:
        if contract["value_type"] != "object":
            flattened.append(deepcopy(contract))
            continue
        fields = contract.get("object_fields")
        if not fields:
            raise ValueError(f"v21_object_fields_missing:{contract['slot_id']}")
        for field in fields:
            flattened.append(
                {
                    **{
                        key: value
                        for key, value in contract.items()
                        if key not in {"member_contract", "object_fields", "value_type"}
                    },
                    **field,
                    "slot_id": f"{contract['slot_id']}::{field['field_id']}",
                    "predicate_id": f"{contract['predicate_id']}::{field['field_id']}",
                    "parent_object_slot": contract["slot_id"],
                    "value_type": field["value_type"],
                }
            )
    return flattened


def _canonical_member_id(value: str, index: int) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return token or f"member_{index:04d}"


def lower_grounded_collection_envelopes(
    model_output: dict[str, Any], contracts: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    """Structurally expand explicitly allowed shared-grounding list envelopes.

    Member text, evidence handle, and source quote remain model-authored. No member is
    added, deleted, paraphrased, or semantically inferred.
    """
    lowered = deepcopy(model_output)
    by_slot = {item["slot_id"]: item for item in contracts}
    adapted: list[str] = []
    for slot in lowered.get("slots", []):
        contract = by_slot.get(slot.get("slot_id"))
        if not contract or contract.get("value_type") != "array":
            continue
        values = slot.get("value")
        if (
            not values
            or not isinstance(values, list)
            or not all(isinstance(value, str) and value.strip() for value in values)
        ):
            continue
        if contract.get("collection_input_shape") != "grounded_string_envelope":
            raise ValueError(f"v21_collection_envelope_not_contracted:{slot['slot_id']}")
        handle = slot.get("evidence_handle")
        verbatim = slot.get("verbatim_value")
        if not isinstance(handle, str) or not isinstance(verbatim, str) or not verbatim:
            raise ValueError(f"v21_collection_envelope_grounding_missing:{slot['slot_id']}")
        slot["value"] = [
            {
                "canonical_id": _canonical_member_id(value, index),
                "evidence_handle": handle,
                "verbatim_value": value,
            }
            for index, value in enumerate(values, start=1)
        ]
        del slot["evidence_handle"]
        del slot["verbatim_value"]
        adapted.append(slot["slot_id"])
    return lowered, adapted


def validate_required_qualifiers(
    *, model_output: dict[str, Any], contracts: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> None:
    evidence_index = {item["handle"]: item for item in evidence}
    emitted = {item["slot_id"]: item for item in model_output.get("slots", [])}
    for contract in contracts:
        required = contract.get("required_qualifier_literals", [])
        if not required:
            continue
        slot = emitted.get(contract["slot_id"])
        if slot is None:
            raise ValueError(f"v21_qualifier_slot_missing:{contract['slot_id']}")
        span = slot.get("verbatim_value", "")
        source = evidence_index.get(slot.get("evidence_handle"), {}).get("verbatim_text", "")
        for literal in required:
            if not unicode_equivalent_substring(literal, span):
                raise ValueError(f"v21_required_qualifier_missing:{contract['slot_id']}:{literal}")
            if not unicode_equivalent_substring(literal, source):
                raise ValueError(
                    f"v21_required_qualifier_not_grounded:{contract['slot_id']}:{literal}"
                )


def validate_and_project_slots_v21(
    *,
    model_output: dict[str, Any],
    evidence: list[dict[str, Any]],
    required_slots: list[dict[str, Any]],
    framework_subject: dict[str, str],
) -> dict[str, Any]:
    lowered, adapted = lower_grounded_collection_envelopes(model_output, required_slots)
    validate_required_qualifiers(model_output=lowered, contracts=required_slots, evidence=evidence)
    projection_contracts = deepcopy(required_slots)
    for contract in projection_contracts:
        contract.pop("collection_input_shape", None)
    result = validate_and_project_slots(
        model_output=lowered,
        evidence=evidence,
        required_slots=projection_contracts,
        framework_subject=framework_subject,
    )
    result["v21_structural_adapters"] = adapted
    result["candidate_semantics_modified"] = False
    result["candidate_surface_shape_lowered"] = bool(adapted)
    return result
