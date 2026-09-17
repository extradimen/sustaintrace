from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from .v15_grounding import unicode_equivalent_substring
from .v20_collection_projection import project_collection_slot
from .v23_preflight import ground_ordered_string_span_v23


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _numeric_tokens(value: str) -> list[float]:
    tokens = re.findall(
        r"[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
        r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:\.\d+)?(?!,\d)|\d+(?:\.\d+)?)",
        value,
    )
    return [float(re.sub(r"[, \u00a0\u202f]", "", token)) for token in tokens]


def slot_output_schema(
    available_handles: list[str], required_slots: list[dict[str, Any]]
) -> dict[str, Any]:
    if not available_handles or len(available_handles) != len(set(available_handles)):
        raise ValueError("v13_handles_must_be_nonempty_and_unique")
    slot_ids = [item["slot_id"] for item in required_slots]
    if not slot_ids or len(slot_ids) != len(set(slot_ids)):
        raise ValueError("v13_slot_ids_must_be_nonempty_and_unique")
    item_schemas = []
    json_types = {"number": "number", "string": "string", "boolean": "boolean"}
    for contract in required_slots:
        value_type = contract["value_type"]
        if value_type in {"array", "object"}:
            if (
                value_type == "array"
                and contract.get("collection_input_shape") == "grounded_string_envelope"
            ):
                item_schemas.append(
                    {
                        "type": "object",
                        "required": [
                            "slot_id",
                            "value",
                            "verbatim_value",
                            "evidence_handle",
                        ],
                        "properties": {
                            "slot_id": {"const": contract["slot_id"]},
                            "value": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            },
                            "verbatim_value": {"type": "string", "minLength": 1},
                            "evidence_handle": {"enum": sorted(available_handles)},
                        },
                        "additionalProperties": False,
                    }
                )
                continue
            member_schema = {
                "type": "object",
                "required": ["evidence_handle", "verbatim_value"],
                "properties": {
                    "canonical_id": {"type": "string", "minLength": 1},
                    "evidence_handle": {"enum": sorted(available_handles)},
                    "verbatim_value": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            }
            if value_type == "array":
                member_schema["required"] = [
                    "canonical_id",
                    "evidence_handle",
                    "verbatim_value",
                ]
                value_schema = {
                    "type": "array",
                    "minItems": 1,
                    "items": member_schema,
                }
            else:
                value_schema = {
                    "type": "object",
                    "minProperties": 1,
                    "additionalProperties": member_schema,
                }
            required = ["slot_id", "value"]
            properties = {
                "slot_id": {"const": contract["slot_id"]},
                "value": value_schema,
            }
        elif value_type == "string" and contract.get("string_input_shape") == "ordered_span":
            required = ["slot_id", "value", "fragments"]
            properties = {
                "slot_id": {"const": contract["slot_id"]},
                "value": {"type": "string", "minLength": 1},
                "fragments": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "required": ["evidence_handle", "verbatim_value"],
                        "properties": {
                            "evidence_handle": {"enum": sorted(available_handles)},
                            "verbatim_value": {"type": "string", "minLength": 1},
                        },
                        "additionalProperties": False,
                    },
                },
            }
        else:
            required = ["slot_id", "value", "verbatim_value", "evidence_handle"]
            properties = {
                "slot_id": {"const": contract["slot_id"]},
                "value": (
                    {
                        "anyOf": [
                            {"type": "number"},
                            {
                                "type": "string",
                                "pattern": r"^-?\d[\d,]*(?:\.\d+)?$",
                            },
                        ]
                    }
                    if value_type == "number"
                    else {"type": json_types[value_type]}
                ),
                "verbatim_value": {"type": "string", "minLength": 1},
                "evidence_handle": {"enum": sorted(available_handles)},
            }
        item_schemas.append(
            {
                "type": "object",
                "required": required,
                "properties": properties,
                "additionalProperties": False,
            }
        )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["slots"],
        "properties": {
            "slots": {
                "type": "array",
                "minItems": len(slot_ids),
                "maxItems": len(slot_ids),
                "items": {"oneOf": item_schemas},
            }
        },
        "additionalProperties": False,
    }


def validate_and_project_slots(
    *,
    model_output: Any,
    evidence: list[dict[str, Any]],
    required_slots: list[dict[str, Any]],
    framework_subject: dict[str, str],
) -> dict[str, Any]:
    """Project model-filled values through framework-owned semantic slots."""
    schema = slot_output_schema([item["handle"] for item in evidence], required_slots)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"v13_slot_schema_failure:{errors[0].message}")
    by_slot = {item["slot_id"]: item for item in model_output["slots"]}
    if len(by_slot) != len(model_output["slots"]):
        raise ValueError("v13_duplicate_slot_id")
    missing = [item["slot_id"] for item in required_slots if item["slot_id"] not in by_slot]
    if missing:
        raise ValueError(f"v13_required_slots_missing:{missing}")
    evidence_index = {item["handle"]: item for item in evidence}
    claims = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    subject_id = framework_subject["entity_id"]
    nodes.append({"id": subject_id, "type": "entity", "label": framework_subject["entity_label"]})
    for index, contract in enumerate(required_slots, start=1):
        emitted = by_slot[contract["slot_id"]]
        expected_type = contract["value_type"]
        if expected_type in {"array", "object"}:
            projected = project_collection_slot(
                slot_id=contract["slot_id"],
                predicate_id=contract["predicate_id"],
                value_type=expected_type,
                value=emitted["value"],
                evidence=evidence,
            )
            for member_index, atomic in enumerate(projected["atomic_claims"], start=1):
                claim_id = f"CLAIM-{index:04d}-{member_index:04d}"
                observation_id = f"OBS::{claim_id}"
                claim = {
                    **atomic,
                    "claim_id": claim_id,
                    "subject_id": subject_id,
                    "subject_label": framework_subject["entity_label"],
                    "value_type": "collection_member",
                    "source_verbatim_preserved": True,
                    "field_ownership": {
                        "subject": "framework_source_registry",
                        "predicate_id": "frozen_slot_contract",
                        "member_id": "model_emitted_and_frozen_member_contract",
                    },
                }
                claims.append(claim)
                nodes.append(
                    {
                        "id": observation_id,
                        "type": "observation",
                        "predicate_id": contract["predicate_id"],
                        "member_id": atomic["member_id"],
                        "evidence_handle": atomic["evidence_handle"],
                    }
                )
                edges.append(
                    {"source": subject_id, "relation": "asserts", "target": observation_id}
                )
            continue
        value = emitted["value"]
        model_emitted_value = value
        span_grounding = None
        if expected_type == "string" and contract.get("string_input_shape") == "ordered_span":
            span_grounding = ground_ordered_string_span_v23(
                value=value,
                fragments=emitted["fragments"],
                evidence=evidence,
                required_terms=contract.get("required_value_terms", []),
                max_handle_gap=contract.get("max_handle_gap", 1),
            )
            verbatim = " ".join(
                _normalized(item["verbatim_value"]) for item in emitted["fragments"]
            )
            evidence_handle = emitted["fragments"][0]["evidence_handle"]
        else:
            source = evidence_index[emitted["evidence_handle"]]
            verbatim = _normalized(emitted["verbatim_value"])
            source_text = _normalized(source["verbatim_text"])
            if not unicode_equivalent_substring(verbatim, source_text):
                raise ValueError(f"v13_verbatim_not_grounded:{contract['slot_id']}")
            evidence_handle = emitted["evidence_handle"]
        if expected_type == "number":
            if isinstance(value, str):
                value = float(value.replace(",", ""))
                if value.is_integer():
                    value = int(value)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"v13_slot_type_mismatch:{contract['slot_id']}")
            comparison_value = (
                abs(float(value)) if contract.get("direction") == "decrease" else float(value)
            )
            if not any(
                math.isclose(comparison_value, token, rel_tol=1e-9, abs_tol=1e-9)
                for token in _numeric_tokens(verbatim)
            ):
                raise ValueError(f"v13_numeric_not_grounded:{contract['slot_id']}")
        elif expected_type == "string" and span_grounding is None:
            if not isinstance(value, str):
                raise ValueError(f"v13_slot_type_mismatch:{contract['slot_id']}")
            if _normalized(value).casefold() not in verbatim.casefold():
                raise ValueError(f"v13_string_not_grounded:{contract['slot_id']}")
            required_terms = contract.get("required_value_terms", [])
            if not all(term.casefold() in verbatim.casefold() for term in required_terms):
                raise ValueError(f"v13_required_value_terms_missing:{contract['slot_id']}")
        elif expected_type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"v13_slot_type_mismatch:{contract['slot_id']}")
        claim_id = f"CLAIM-{index:04d}"
        observation_id = f"OBS::{claim_id}"
        claim = {
            "claim_id": claim_id,
            "slot_id": contract["slot_id"],
            "subject_id": subject_id,
            "subject_label": framework_subject["entity_label"],
            "predicate_id": contract["predicate_id"],
            "value": value,
            "model_emitted_value": model_emitted_value,
            "value_type": expected_type,
            "canonical_unit": contract.get("canonical_unit"),
            "period": contract.get("period"),
            "scope_id": contract.get("scope_id"),
            "claim_kind": contract.get("claim_kind", "observed"),
            "comparison_operator": contract.get("comparison_operator"),
            "direction": contract.get("direction"),
            "normalized_signed_value": (
                -abs(float(value))
                if expected_type == "number" and contract.get("direction") == "decrease"
                else value
            ),
            "evidence_handle": evidence_handle,
            "evidence_handles": (
                span_grounding["evidence_handles"] if span_grounding is not None else None
            ),
            "verbatim_value": verbatim,
            "grounding_comparison": "unicode_nfkc_apostrophe_equivalence",
            "source_verbatim_preserved": True,
            "field_ownership": {
                "subject": "framework_source_registry",
                "predicate_id": "frozen_slot_contract",
                "value": "model_emitted_numeric_literal_deterministically_normalized_and_grounded",
                "canonical_unit": "frozen_slot_contract",
                "period": "frozen_slot_contract",
                "scope_id": "frozen_slot_contract",
                "comparison_operator": "frozen_slot_contract",
                "direction": "frozen_slot_contract",
            },
        }
        claims.append(claim)
        nodes.append(
            {
                "id": observation_id,
                "type": "observation",
                "predicate_id": contract["predicate_id"],
                "value": value,
                "canonical_unit": contract.get("canonical_unit"),
                "period": contract.get("period"),
                "scope_id": contract.get("scope_id"),
                "comparison_operator": contract.get("comparison_operator"),
                "direction": contract.get("direction"),
                "evidence_handle": evidence_handle,
                "evidence_handles": (
                    span_grounding["evidence_handles"]
                    if span_grounding is not None
                    else None
                ),
            }
        )
        edges.append({"source": subject_id, "relation": "asserts", "target": observation_id})
    return {
        "pipeline_version": "ESG-RD-v1.3-SLOT-ATOMIC-PROJECTION",
        "validated_claims": claims,
        "knowledge_graph": {"nodes": nodes, "edges": edges},
        "task_coverage": {
            "required_slot_count": len(required_slots),
            "covered_slot_count": len(claims),
            "complete": True,
        },
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }
