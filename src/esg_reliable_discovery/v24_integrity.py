from __future__ import annotations

import re
import unicodedata
from typing import Any

from jsonschema import Draft202012Validator

from .v13_atomic_projection import slot_output_schema
from .v20_contracts import validate_slot_contracts_before_candidate
from .v21_contract_adapters import (
    flatten_object_contracts,
    validate_and_project_slots_v21,
)


def validate_layout_registry_v24(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Require the production one-task-per-record layout shape before inference."""
    if not records:
        raise ValueError("v24_layout_registry_empty")
    seen: set[tuple[str, int]] = set()
    checked = []
    for index, record in enumerate(records):
        if "task_ids" in record:
            raise ValueError(f"v24_layout_registry_compact_task_ids:{index}")
        task_id = record.get("task_id")
        page = record.get("pdf_page", record.get("page"))
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"v24_layout_registry_task_id_missing:{index}")
        if not isinstance(page, int) or page < 1:
            raise ValueError(f"v24_layout_registry_page_invalid:{index}")
        key = (task_id, page)
        if key in seen:
            raise ValueError(f"v24_layout_registry_duplicate:{task_id}:{page}")
        seen.add(key)
        checked.append({"task_id": task_id, "pdf_page": page})
    return {"status": "passed", "record_count": len(checked), "records": checked}


def _metric_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _canonical_unit(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    key = re.sub(r"[^a-z0-9]", "", normalized.casefold())
    if key in {"tco2e", "tco2eq", "tonnesco2e", "tonnesco2eq"}:
        return "tCO2e"
    return value


def _match_role(metric: str, role_ids: list[str]) -> str:
    metric_tokens = set(_metric_key(metric).split())
    ranked = []
    for role_id in role_ids:
        role_tokens = set(_metric_key(role_id).split())
        score = len(role_tokens & metric_tokens)
        if role_id == "market_scope_2" and {"market", "scope", "2"} <= metric_tokens:
            score += 10
        elif role_id == "scope_1" and {"scope", "1"} <= metric_tokens:
            score += 10
        elif role_id == "scope_3" and {"scope", "3"} <= metric_tokens:
            score += 10
        ranked.append((score, role_id))
    ranked.sort(reverse=True)
    if not ranked or ranked[0][0] <= 0:
        raise ValueError(f"v24_calculation_metric_unmatched:{metric}")
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise ValueError(f"v24_calculation_metric_ambiguous:{metric}")
    return ranked[0][1]


def normalize_calculation_binding_v24(
    model_output: dict[str, Any], plan: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Lower a legacy calculation request to bindings without trusting its operation."""
    if "observations" in model_output:
        return model_output, {
            "adapter_applied": False,
            "candidate_operation_fields_ignored": [],
        }
    request = model_output.get("calculation_request")
    if not isinstance(request, dict):
        raise ValueError("v24_calculation_binding_shape_unsupported")
    role_ids = [role["role_id"] for role in plan.get("roles", [])]
    reported_roles = [role_id for role_id in role_ids if role_id == "reported_total"]
    observations: dict[str, Any] = {}
    for item in request.get("inputs", []):
        if not isinstance(item, dict):
            raise ValueError("v24_calculation_input_invalid")
        role_id = _match_role(str(item.get("metric", "")), role_ids)
        if role_id in observations:
            raise ValueError(f"v24_calculation_role_duplicate:{role_id}")
        observations[role_id] = {
            "value": item["value"],
            "evidence_handle": item["evidence_handle"],
            "period_year": item["period_year"],
            "unit": _canonical_unit(str(request.get("unit", item.get("unit", "")))),
        }
    comparison = request.get("comparison_value")
    if reported_roles and isinstance(comparison, dict):
        observations[reported_roles[0]] = {
            "value": comparison["value"],
            "evidence_handle": comparison["evidence_handle"],
            "period_year": comparison["period_year"],
            "unit": _canonical_unit(
                str(request.get("unit", comparison.get("unit", "")))
            ),
        }
    missing = [role_id for role_id in role_ids if role_id not in observations]
    if missing:
        raise ValueError(f"v24_calculation_roles_missing:{missing}")
    ignored = [
        key
        for key in ("operation", "calculated_sum", "difference", "explanation")
        if key in request
    ]
    return {"observations": observations}, {
        "adapter_applied": True,
        "source_shape": "legacy_calculation_request",
        "candidate_operation_fields_ignored": ignored,
        "candidate_semantics_modified": False,
        "framework_operation_remains_frozen": True,
    }


def _fixture_for_contract_v24(
    contract: dict[str, Any], handles: list[str]
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    slot_id = contract["slot_id"]
    value_type = contract["value_type"]
    required = list(
        dict.fromkeys(
            [
                *contract.get("required_qualifier_literals", []),
                *contract.get("required_value_terms", []),
            ]
        )
    )
    grounded = "fixture " + " ".join(required)
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
    if value_type == "string" and contract.get("string_input_shape") == "ordered_span":
        if len(handles) != 2:
            raise ValueError(f"v24_ordered_span_fixture_handles:{slot_id}")
        midpoint = max(1, len(required) // 2)
        left_terms = required[:midpoint]
        right_terms = required[midpoint:]
        left = "fixture " + " ".join(left_terms)
        right = " ".join(right_terms) or "span"
        return {
            "slot_id": slot_id,
            "value": f"{left} {right}",
            "fragments": [
                {"verbatim_value": left, "evidence_handle": handle},
                {"verbatim_value": right, "evidence_handle": handles[1]},
            ],
        }, [(handle, left), (handles[1], right)]
    if value_type == "string":
        return {
            "slot_id": slot_id,
            "value": grounded,
            "verbatim_value": grounded,
            "evidence_handle": handle,
        }, [(handle, grounded)]
    if value_type != "array":
        raise ValueError(f"v24_unlowered_contract_type:{slot_id}:{value_type}")
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


def dry_run_stage_b_contracts_v24(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    """Run candidate schema and projector with fixtures covering every required term."""
    validate_slot_contracts_before_candidate(contracts)
    flattened = flatten_object_contracts(contracts)
    validate_slot_contracts_before_candidate(flattened)
    handle_groups = [
        [
            f"P001-V24-{index:04d}",
            *(
                [f"P001-V24-{index:04d}-SPAN2"]
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
        fixture, sources = _fixture_for_contract_v24(contract, group)
        slots.append(fixture)
        for handle, source_text in sources:
            evidence.append(
                {
                    "handle": handle,
                    "source_id": "V24-PREFLIGHT",
                    "page": 1,
                    "verbatim_text": source_text,
                    "normalized_text": source_text,
                }
            )
    projected = validate_and_project_slots_v21(
        model_output={"slots": slots},
        evidence=evidence,
        required_slots=flattened,
        framework_subject={"entity_id": "V24-PREFLIGHT", "entity_label": "fixture"},
    )
    return {
        "status": "passed",
        "raw_contract_count": len(contracts),
        "candidate_contract_count": len(flattened),
        "schema_valid": True,
        "projector_valid": True,
        "validated_fixture_claim_count": len(projected["validated_claims"]),
        "required_value_terms_in_fixture": True,
        "candidate_inference_released": True,
    }
