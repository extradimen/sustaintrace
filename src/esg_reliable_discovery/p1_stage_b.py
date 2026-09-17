from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator


def stage_b_schema(
    available_handles: list[str], ontology: dict[str, Any]
) -> dict[str, Any]:
    if not available_handles or len(set(available_handles)) != len(available_handles):
        raise ValueError("stage_b_handles_must_be_nonempty_and_unique")
    metrics = ontology.get("metrics", {})
    units = ontology.get("units", {})
    scopes = ontology.get("scopes", {})
    if not metrics or not units or not scopes:
        raise ValueError("stage_b_ontology_is_empty")
    claim = {
        "type": "object",
        "required": [
            "metric_id", "normalized_value", "verbatim_value",
            "canonical_unit", "period_year", "scope_id", "claim_kind",
            "evidence_handle",
        ],
        "properties": {
            "metric_id": {"enum": sorted(metrics)},
            "normalized_value": {"type": ["number", "string"]},
            "verbatim_value": {"type": "string", "minLength": 1},
            "canonical_unit": {"enum": sorted(units)},
            "period_year": {"type": "integer", "minimum": 1900, "maximum": 2200},
            "scope_id": {"enum": sorted(scopes)},
            "claim_kind": {"enum": ["observed", "target"]},
            "evidence_handle": {"enum": available_handles},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "P1 Stage B atomic ESG claims",
        "type": "object",
        "required": ["claims"],
        "properties": {"claims": {"type": "array", "minItems": 1, "items": claim}},
        "additionalProperties": False,
    }


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _numeric_tokens(value: str) -> list[float]:
    return [
        float(token.replace(",", ""))
        for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
    ]


def validate_and_project_stage_b(
    model_output: Any, evidence: list[dict[str, Any]], ontology: dict[str, Any],
    framework_subject: dict[str, str],
) -> dict[str, Any]:
    schema = stage_b_schema([item["handle"] for item in evidence], ontology)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(model_output),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"stage_b_schema_failure:{errors[0].message}")
    evidence_index = {item["handle"]: item for item in evidence}
    validated = []
    nodes: dict[str, dict[str, Any]] = {}
    edges = []
    for index, claim in enumerate(model_output["claims"], start=1):
        source = evidence_index[claim["evidence_handle"]]
        verbatim = _normalized_text(claim["verbatim_value"])
        source_text = _normalized_text(source["verbatim_text"])
        if verbatim not in source_text:
            raise ValueError(f"stage_b_verbatim_value_not_grounded:{claim['evidence_handle']}")
        value = claim["normalized_value"]
        if isinstance(value, (int, float)) and not any(
            math.isclose(float(value), token, rel_tol=1e-9, abs_tol=1e-9)
            for token in _numeric_tokens(verbatim)
        ):
            raise ValueError(f"stage_b_numeric_value_not_grounded:{claim['evidence_handle']}")
        year_context = " ".join(filter(None, [
            source_text, source.get("table_header_context"),
        ]))
        if str(claim["period_year"]) not in year_context:
            raise ValueError(f"stage_b_period_not_grounded:{claim['evidence_handle']}")
        metric = ontology["metrics"][claim["metric_id"]]
        if claim["canonical_unit"] not in metric["allowed_units"]:
            raise ValueError(f"stage_b_unit_not_allowed:{claim['metric_id']}")
        if claim["scope_id"] not in metric["allowed_scopes"]:
            raise ValueError(f"stage_b_scope_not_allowed:{claim['metric_id']}")
        claim_id = f"CLAIM-{index:04d}"
        validated.append({
            **claim,
            "subject_id": framework_subject["entity_id"],
            "subject_label": framework_subject["entity_label"],
            "claim_id": claim_id,
            "field_support": {
                "evidence_handle": "deterministically_grounded",
                "verbatim_value": "deterministically_grounded",
                "normalized_value": "deterministically_grounded",
                "period_year": "deterministically_grounded",
                "canonical_unit": "ontology_constrained",
                "subject": "framework_resolved_from_frozen_source_registry",
                "metric_id": "ontology_constrained_semantic",
                "scope_id": "ontology_constrained_semantic",
                "claim_kind": "ontology_constrained_semantic",
            },
        })
        subject_id = framework_subject["entity_id"]
        metric_id = f"METRIC::{claim['metric_id']}"
        observation_id = f"OBS::{claim_id}"
        nodes[subject_id] = {
            "id": subject_id, "type": "entity",
            "label": framework_subject["entity_label"],
        }
        nodes[metric_id] = {"id": metric_id, "type": "metric", "label": metric["label"]}
        nodes[observation_id] = {
            "id": observation_id, "type": "observation",
            "value": value, "unit": claim["canonical_unit"],
            "period_year": claim["period_year"], "scope_id": claim["scope_id"],
            "claim_kind": claim["claim_kind"],
            "evidence_handle": claim["evidence_handle"],
        }
        edges.extend([
            {"source": subject_id, "relation": "reports", "target": observation_id},
            {"source": observation_id, "relation": "measures", "target": metric_id},
        ])
    return {
        "model_output": model_output,
        "validated_claims": validated,
        "knowledge_graph": {"nodes": list(nodes.values()), "edges": edges},
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
        "human_validation_claimed": False,
    }
