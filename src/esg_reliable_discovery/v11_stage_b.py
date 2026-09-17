from __future__ import annotations

import re
from typing import Any

from .v1_stage_b import validate_and_project_v1


def validate_and_project_v11(
    model_output: Any,
    evidence: list[dict[str, Any]],
    ontology: dict[str, Any],
    framework_subject: dict[str, str],
    required_claims: list[dict[str, Any]],
    document_reporting_year: int,
) -> dict[str, Any]:
    """Permit auditable report-year inheritance only for qualifying observations."""
    qualifying = {
        (item["metric_id"], item.get("claim_kind", "observed"), item.get("period_year"))
        for item in required_claims
        if item.get("claim_kind", "observed") == "observed"
        and item.get("period_year") == document_reporting_year
    }
    augmented = [dict(item) for item in evidence]
    evidence_index = {item["handle"]: item for item in augmented}
    links = []
    for claim in model_output.get("claims", []) if isinstance(model_output, dict) else []:
        key = (claim.get("metric_id"), claim.get("claim_kind"), claim.get("period_year"))
        if key not in qualifying:
            continue
        source = evidence_index.get(claim.get("evidence_handle"))
        if source is None:
            continue
        context = " ".join(
            filter(None, [source.get("verbatim_text"), source.get("table_header_context")])
        )
        explicit_years = {int(year) for year in re.findall(r"\b20\d{2}\b", context)}
        if explicit_years and document_reporting_year not in explicit_years:
            continue
        if document_reporting_year not in explicit_years:
            prior = source.get("table_header_context") or ""
            source["table_header_context"] = f"{prior} {document_reporting_year}".strip()
            links.append(
                {
                    "evidence_handle": source["handle"],
                    "period_year": document_reporting_year,
                    "rule": "frozen_document_reporting_year_for_required_observation",
                }
            )
    result = validate_and_project_v1(
        model_output, augmented, ontology, framework_subject, required_claims
    )
    result["reporting_year_inheritance"] = links
    result["pipeline_version"] = "ESG-RD-v1.1-TABLE-AND-PERIOD"
    return result
