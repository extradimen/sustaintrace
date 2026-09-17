from __future__ import annotations

import json

from esg_reliable_discovery.p1_gates import audit_p1_gates


def test_open_registry_blocks_inference(tmp_path):
    plan = {
        "plan_id": "P1",
        "target_report_count": 1,
        "excluded_companies": ["P0 Corp"],
        "gates": {
            "source_registry_frozen": False,
            "sample_manifest_frozen": False,
            "task_pack_frozen": False,
            "annotation_agreement_complete": False,
            "gold_lock_created": False,
            "model_configuration_frozen": False,
            "inference_allowed": False,
        },
    }
    registry = {
        "registry_id": "R1",
        "candidates": [
            {
                "candidate_id": "C1",
                "company": "New Corp",
                "official_url": "https://example.com/report.pdf",
                "region": "Europe",
                "exposure_stratum": "high_environmental_exposure",
                "eligibility_status": "pending",
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    registry_path = tmp_path / "registry.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = audit_p1_gates(plan_path, registry_path)

    assert result["candidate_count"] == 1
    assert result["eligible_count"] == 0
    assert result["gate_state_consistent"] is True
    assert result["inference_allowed"] is False


def test_eligible_candidate_must_match_acquisition_provenance(tmp_path):
    plan = {
        "plan_id": "P1",
        "target_report_count": 1,
        "excluded_companies": [],
        "gates": {"inference_allowed": False},
    }
    registry = {
        "registry_id": "R1",
        "candidates": [{
            "candidate_id": "C1", "company": "Company A", "region": "Europe",
            "exposure_stratum": "high_environmental_exposure",
            "official_url": "https://example.com/a.pdf", "eligibility_status": "eligible",
            "document_id": "DOC-A", "sha256": "wrong", "page_count": 10,
        }],
    }
    acquisition = {"documents": [{
        "document_id": "DOC-A", "company_name": "Company A", "sha256": "right",
        "page_count": 10, "ingestion_status": "verified",
    }]}
    paths = [tmp_path / name for name in ("plan.json", "registry.json", "acquisition.json")]
    for path, value in zip(paths, (plan, registry, acquisition), strict=True):
        path.write_text(json.dumps(value), encoding="utf-8")

    result = audit_p1_gates(*paths)

    assert result["source_readiness_checks"][
        "all_eligible_provenance_matches_acquisition_manifest"
    ] is False


def test_inconsistent_inference_gate_is_detected(tmp_path):
    plan = {
        "plan_id": "P1",
        "target_report_count": 0,
        "excluded_companies": [],
        "gates": {"inference_allowed": True},
    }
    registry = {"registry_id": "R1", "candidates": []}
    plan_path = tmp_path / "plan.json"
    registry_path = tmp_path / "registry.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    result = audit_p1_gates(plan_path, registry_path)

    assert result["computed_inference_allowed"] is False
    assert result["gate_state_consistent"] is False
