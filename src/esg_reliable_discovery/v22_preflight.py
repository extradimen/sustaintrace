from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from .v13_atomic_projection import slot_output_schema
from .v20_contracts import validate_slot_contracts_before_candidate
from .v21_contract_adapters import (
    flatten_object_contracts,
    validate_and_project_slots_v21,
)


def _fixture_for_contract(
    contract: dict[str, Any], handles: list[str]
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    slot_id = contract["slot_id"]
    value_type = contract["value_type"]
    qualifiers = contract.get("required_qualifier_literals", [])
    grounded = "fixture " + " ".join(qualifiers)
    handle = handles[0]
    if value_type == "number":
        return {
            "slot_id": slot_id,
            "value": 1,
            "verbatim_value": "1",
            "evidence_handle": handle,
        }, [(handle, "1")]
    if value_type == "boolean":
        return {
            "slot_id": slot_id,
            "value": True,
            "verbatim_value": grounded,
            "evidence_handle": handle,
        }, [(handle, grounded)]
    if value_type == "string":
        if contract.get("string_input_shape") == "ordered_span":
            if len(handles) != 2:
                raise ValueError(f"v22_ordered_span_fixture_handles:{slot_id}")
            second = grounded.removeprefix("fixture ") or "span"
            return {
                "slot_id": slot_id,
                "value": f"fixture {second}",
                "fragments": [
                    {"verbatim_value": "fixture", "evidence_handle": handle},
                    {"verbatim_value": second, "evidence_handle": handles[1]},
                ],
            }, [(handle, "fixture"), (handles[1], second)]
        return {
            "slot_id": slot_id,
            "value": grounded,
            "verbatim_value": grounded,
            "evidence_handle": handle,
        }, [(handle, grounded)]
    if value_type != "array":
        raise ValueError(f"v22_unlowered_contract_type:{slot_id}:{value_type}")
    if contract.get("collection_input_shape") == "grounded_string_envelope":
        return {
            "slot_id": slot_id,
            "value": ["fixture"],
            "verbatim_value": grounded,
            "evidence_handle": handle,
        }, [(handle, grounded)]
    member = {
        "canonical_id": "fixture",
        "evidence_handle": handle,
        "verbatim_value": "fixture",
    }
    return {"slot_id": slot_id, "value": [member]}, [(handle, "fixture")]


def dry_run_stage_b_contracts_v22(
    contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Exercise the exact candidate-visible schema and projector without a model call."""
    validate_slot_contracts_before_candidate(contracts)
    flattened = flatten_object_contracts(contracts)
    validate_slot_contracts_before_candidate(flattened)
    handle_groups = [
        [
            f"P001-V22-{index:04d}",
            *(
                [f"P001-V22-{index:04d}-SPAN2"]
                if contract.get("string_input_shape") == "ordered_span"
                else []
            ),
        ]
        for index, contract in enumerate(flattened, start=1)
    ]
    handles = [handle for group in handle_groups for handle in group]
    schema = slot_output_schema(handles, flattened)
    Draft202012Validator.check_schema(schema)
    slots = []
    evidence = []
    for contract, group in zip(flattened, handle_groups, strict=True):
        fixture, sources = _fixture_for_contract(contract, group)
        slots.append(fixture)
        for handle, source_text in sources:
            evidence.append(
                {
                    "handle": handle,
                    "source_id": "V22-PREFLIGHT",
                    "page": 1,
                    "verbatim_text": source_text,
                    "normalized_text": source_text,
                }
            )
    projected = validate_and_project_slots_v21(
        model_output={"slots": slots},
        evidence=evidence,
        required_slots=flattened,
        framework_subject={"entity_id": "V22-PREFLIGHT", "entity_label": "fixture"},
    )
    return {
        "status": "passed",
        "raw_contract_count": len(contracts),
        "candidate_contract_count": len(flattened),
        "schema_valid": True,
        "projector_valid": True,
        "validated_fixture_claim_count": len(projected["validated_claims"]),
        "candidate_inference_released": True,
    }
