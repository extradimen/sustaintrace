from __future__ import annotations

from copy import deepcopy
from typing import Any

from .v27_integrity import build_handle_alias_catalog_v27


def alias_stage_a_evidence_v31(
    packet: dict[str, Any], handles: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    """Expose compact aliases while retaining an executor-owned canonical catalog."""
    canonical = [item["handle"] for item in handles]
    catalog = build_handle_alias_catalog_v27(canonical)
    reverse = {handle: alias for alias, handle in catalog.items()}
    prepared = deepcopy(packet)
    blocks = prepared.get("evidence_blocks", [])
    if len(blocks) != len(handles):
        raise ValueError("v31_packet_handle_count_mismatch")
    for block in blocks:
        handle = block.get("handle")
        if handle not in reverse:
            raise ValueError(f"v31_packet_handle_unknown:{handle}")
        block["handle"] = reverse[handle]
    return prepared, catalog, {
        "status": "passed",
        "alias_count": len(catalog),
        "canonical_handles_hidden_from_candidate_selection": True,
        "approximate_handle_repair": False,
        "candidate_semantics_modified": False,
    }


def decode_stage_a_aliases_v31(
    model_output: dict[str, Any], catalog: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode exact aliases in handle fields; reject every unknown approximation."""
    decoded = deepcopy(model_output)
    emitted: list[str] = []

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                if child_key == "evidence_handle" and isinstance(child, str):
                    emitted.append(child)
                    if child not in catalog:
                        raise ValueError(f"v31_unknown_evidence_alias:{child}")
                    value[child_key] = catalog[child]
                elif child_key == "comparison_evidence_handle" and isinstance(child, str):
                    emitted.append(child)
                    if child not in catalog:
                        raise ValueError(f"v31_unknown_evidence_alias:{child}")
                    value[child_key] = catalog[child]
                elif child_key == "evidence_handles" and isinstance(child, list):
                    for alias in child:
                        emitted.append(str(alias))
                        if alias not in catalog:
                            raise ValueError(f"v31_unknown_evidence_alias:{alias}")
                    value[child_key] = [catalog[alias] for alias in child]
                else:
                    visit(child, child_key)
        elif isinstance(value, list):
            for child in value:
                visit(child, key)

    visit(decoded)
    return decoded, {
        "status": "passed",
        "emitted_aliases": emitted,
        "decoded_handles": [catalog[item] for item in emitted],
        "approximate_handle_repair": False,
        "candidate_output_archived_unchanged": True,
        "semantic_values_modified": False,
    }


def project_calculation_slots_v31(
    execution: dict[str, Any], output_slot_map: list[dict[str, str]]
) -> dict[str, Any]:
    """Project executor values through a frozen one-to-one slot mapping."""
    if execution.get("status") != "passed":
        raise ValueError("v31_calculation_execution_not_passed")
    if not output_slot_map:
        raise ValueError("v31_output_slot_map_empty")
    values = execution.get("values", {})
    slot_ids = [item.get("slot_id") for item in output_slot_map]
    source_ids = [item.get("source_value_id") for item in output_slot_map]
    if (
        any(not isinstance(item, str) or not item for item in slot_ids + source_ids)
        or len(slot_ids) != len(set(slot_ids))
        or len(source_ids) != len(set(source_ids))
    ):
        raise ValueError("v31_output_slot_map_invalid")
    missing = [item for item in source_ids if item not in values]
    if missing:
        raise ValueError(f"v31_output_slot_source_missing:{missing}")
    claims = [
        {
            "slot_id": item["slot_id"],
            "value": values[item["source_value_id"]],
            "source_value_id": item["source_value_id"],
            "value_owner": "deterministic_executor",
        }
        for item in output_slot_map
    ]
    return {
        "status": "passed",
        "validated_claims": claims,
        "frozen_mapping_used": True,
        "candidate_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }
