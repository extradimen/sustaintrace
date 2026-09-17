from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class P1GateError(ValueError):
    pass


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise P1GateError(f"Expected a JSON object: {path}")
    return value


def audit_p1_gates(
    plan_path: str | Path,
    registry_path: str | Path,
    acquisition_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Audit P1 prerequisites without opening or inferring over report content."""
    plan = _load(plan_path)
    registry = _load(registry_path)
    candidates = registry.get("candidates", [])
    if not isinstance(candidates, list):
        raise P1GateError("registry.candidates must be an array")

    ids = [item.get("candidate_id") for item in candidates]
    companies = [item.get("company") for item in candidates]
    excluded = {name.casefold() for name in plan.get("excluded_companies", [])}
    excluded_hits = [
        name for name in companies if isinstance(name, str) and name.casefold() in excluded
    ]
    pdf_shaped_urls = [
        item
        for item in candidates
        if str(item.get("official_url", "")).lower().split("?", 1)[0].endswith(".pdf")
    ]
    eligible = [item for item in candidates if item.get("eligibility_status") == "eligible"]
    acquisition_by_id: dict[str, dict[str, Any]] = {}
    if acquisition_manifest_path:
        acquisition = _load(acquisition_manifest_path)
        acquisition_by_id = {
            item["document_id"]: item for item in acquisition.get("documents", [])
        }
    provenance_matches = []
    eligible_pdf_responses = []
    for item in eligible:
        acquired = acquisition_by_id.get(item.get("document_id"))
        provenance_matches.append(
            acquired is not None
            and acquired.get("company_name") == item.get("company")
            and acquired.get("sha256") == item.get("sha256")
            and acquired.get("page_count") == item.get("page_count")
            and acquired.get("ingestion_status") == "verified"
        )
        eligible_pdf_responses.append(
            acquired is not None
            and acquired.get("content_type") == "application/pdf"
            and acquired.get("ingestion_status") == "verified"
        )
    strata = Counter(item.get("exposure_stratum") for item in eligible)
    regions = Counter(item.get("region") for item in eligible)
    target = int(plan.get("target_report_count", 0))

    checks = {
        "candidate_ids_unique": len(ids) == len(set(ids)) and all(ids),
        "companies_unique": len(companies) == len(set(companies)) and all(companies),
        "excluded_companies_absent": not excluded_hits,
        "candidate_pool_at_least_target": len(candidates) >= target,
        "eligible_pool_at_least_target": len(eligible) >= target,
        "all_candidates_have_official_urls": all(item.get("official_url") for item in candidates),
        "all_eligible_sources_are_verified_pdf_responses": (
            all(eligible_pdf_responses)
            if acquisition_manifest_path
            else all(item in pdf_shaped_urls for item in eligible)
        ),
        "all_eligible_provenance_matches_acquisition_manifest": (
            all(provenance_matches) if acquisition_manifest_path else not eligible
        ),
        "eligible_strata_support_four_each": all(
            strata.get(name, 0) >= 4
            for name in (
                "high_environmental_exposure",
                "medium_physical_operations",
                "financial_or_digital_services",
            )
        ),
        "eligible_regions_support_three_each": all(
            regions.get(name, 0) >= 3 for name in ("Europe", "North America", "Asia Pacific")
        ),
    }
    gates = plan.get("gates", {})
    inference_prerequisites = [
        "source_registry_frozen",
        "sample_manifest_frozen",
        "task_pack_frozen",
        "annotation_agreement_complete",
        "gold_lock_created",
        "model_configuration_frozen",
    ]
    computed_inference_allowed = all(gates.get(name) is True for name in inference_prerequisites)
    declared_inference_allowed = gates.get("inference_allowed") is True

    return {
        "schema_version": "1.0",
        "plan_id": plan.get("plan_id"),
        "registry_id": registry.get("registry_id"),
        "candidate_count": len(candidates),
        "pdf_shaped_url_count": len(pdf_shaped_urls),
        "eligible_count": len(eligible),
        "eligible_strata": dict(sorted(strata.items())),
        "eligible_regions": dict(sorted(regions.items())),
        "excluded_company_hits": excluded_hits,
        "source_readiness_checks": checks,
        "source_registry_ready": all(checks.values()),
        "declared_gates": gates,
        "computed_inference_allowed": computed_inference_allowed,
        "gate_state_consistent": declared_inference_allowed == computed_inference_allowed,
        "inference_allowed": declared_inference_allowed and computed_inference_allowed,
    }
