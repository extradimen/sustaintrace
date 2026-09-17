from __future__ import annotations

from typing import Any

from .p1_stage_b import _normalized_text, validate_and_project_stage_b


def _metric_is_lexically_grounded(
    claim: dict[str, Any], evidence_index: dict[str, dict[str, Any]], ontology: dict[str, Any]
) -> bool:
    metric = ontology["metrics"][claim["metric_id"]]
    source = evidence_index[claim["evidence_handle"]]
    context = _normalized_text(
        " ".join(
            filter(
                None,
                [source["verbatim_text"], source.get("table_header_context")],
            )
        )
    ).casefold()
    phrases = [item.casefold() for item in metric.get("required_evidence_phrases", [])]
    terms = [item.casefold() for item in metric.get("required_evidence_terms", [])]
    phrase_ok = not phrases or any(phrase in context for phrase in phrases)
    terms_ok = all(term in context for term in terms)
    return phrase_ok and terms_ok


def _claim_covers_requirement(claim: dict[str, Any], requirement: dict[str, Any]) -> bool:
    if claim["metric_id"] != requirement["metric_id"]:
        return False
    if "period_year" in requirement and claim["period_year"] != requirement["period_year"]:
        return False
    if "claim_kind" in requirement and claim["claim_kind"] != requirement["claim_kind"]:
        return False
    return True


def validate_and_project_v1(
    model_output: Any,
    evidence: list[dict[str, Any]],
    ontology: dict[str, Any],
    framework_subject: dict[str, str],
    required_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Add lexical metric grounding and task-coverage gates to frozen Stage B logic."""
    result = validate_and_project_stage_b(model_output, evidence, ontology, framework_subject)
    evidence_index = {item["handle"]: item for item in evidence}
    for claim in result["validated_claims"]:
        if not _metric_is_lexically_grounded(claim, evidence_index, ontology):
            raise ValueError(f"v1_metric_not_lexically_grounded:{claim['metric_id']}")
        claim["field_support"]["metric_id"] = "ontology_and_lexically_grounded"
    missing = [
        requirement
        for requirement in required_claims
        if not any(
            _claim_covers_requirement(claim, requirement) for claim in result["validated_claims"]
        )
    ]
    if missing:
        raise ValueError(f"v1_required_claims_missing:{missing}")
    result["task_coverage"] = {
        "required_claim_count": len(required_claims),
        "covered_claim_count": len(required_claims),
        "complete": True,
        "derived_by": "frozen_task_projection_contract",
    }
    result["pipeline_version"] = "ESG-RD-v1.0-SEMANTIC-PROJECTION"
    return result
