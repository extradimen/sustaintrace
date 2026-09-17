from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from esg_reliable_discovery.knowledge_query import query_facts
from esg_reliable_discovery.release_runtime import initialize_workspace
from esg_reliable_discovery.workbench_api import WorkbenchService


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path
    knowledge = root / "data/knowledge_bases/v0.1"
    knowledge.mkdir(parents=True)
    (knowledge / "fact_records.jsonl").write_text(
        json.dumps({"record_id": "fact-1", "failure_signature": "A"}) + "\n", encoding="utf-8"
    )
    (knowledge / "trusted_fact_records.jsonl").write_text("", encoding="utf-8")
    (knowledge / "failure_records.jsonl").write_text(
        json.dumps({"record_id": "fail-1", "failure_signature": "TABLE"}) + "\n",
        encoding="utf-8",
    )
    return root


def test_summary_uses_current_knowledge_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "esg_reliable_discovery.workbench_api.probe_mineru",
        lambda _executable: {"available": False, "executable": "mineru", "version": None},
    )
    summary = WorkbenchService(_workspace(tmp_path)).summary()
    assert summary["inventory"]["fact_records"] == 1
    assert summary["inventory"]["failure_records"] == 1
    assert summary["inventory"]["failure_signatures"] == 1


def test_release_seed_initializes_without_overwriting_existing_files(tmp_path: Path) -> None:
    existing = tmp_path / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
    existing.parent.mkdir(parents=True)
    existing.write_text("preserve-me\n", encoding="utf-8")
    result = initialize_workspace(tmp_path)
    assert existing.read_text(encoding="utf-8") == "preserve-me\n"
    assert result["counts"]["trusted_facts"] == 149
    assert result["counts"]["relation_edges"] == 149
    assert "trusted_fact_records.jsonl" in result["preserved"]
    assert (existing.parent / "entity_registry.jsonl").is_file()


def test_release_seed_exposes_controlled_entities_and_relations(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    service = WorkbenchService(tmp_path)
    entities = service.entities()
    assert entities["matched"] == 34
    assert entities["policy"]["fuzzy_merge"] is False
    entity_id = entities["records"][0]["entity_id"]
    relations = service.relations(entity_id=entity_id)
    assert relations["matched"] >= 1
    assert {row["subject_entity_id"] for row in relations["records"]} == {entity_id}
    assert all(row["trust_tier"] == "B" for row in relations["records"])
    response = query_facts(tmp_path / "data/knowledge_bases/v0.1", limit=200)
    assert response["inventory"] == {
        "facts": 149,
        "trusted_tier_b": 149,
        "candidates_not_trusted": 0,
    }
    assert response["pagination"]["matched"] == 149
    summary = service.summary()
    assert summary["inventory"]["unique_reports"] == 34
    assert summary["inventory"]["fact_records"] == 149


def test_create_job_freezes_pdf_and_never_authorizes_cloud(tmp_path: Path) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="../report.pdf"
    )
    assert job["state"] == "source_frozen"
    assert job["source"]["original_filename"] == "report.pdf"
    assert job["policy"]["cloud_transfer_authorized"] is False
    assert (tmp_path / job["source"]["local_path"]).read_bytes() == payload


def test_create_job_rejects_non_pdf(tmp_path: Path) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    with pytest.raises(ValueError, match="not a PDF"):
        service.create_job(io.BytesIO(b"hello"), content_length=5, filename="bad.pdf")


def test_analytics_and_schema_use_only_trusted_facts(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    trusted = {
        "record_id": "fact-trusted",
        "subject": {"entity_label": "Example Plc"},
        "predicate": {"canonical_key": "scope_1_emissions"},
        "value": "42",
        "qualifiers": {"reference_period": 2025, "normalized_unit": "tCO2e"},
        "evidence": [{"pdf_page": 10, "quote": "Scope 1 emissions 42"}],
    }
    (root / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl").write_text(
        json.dumps(trusted) + "\n", encoding="utf-8"
    )
    service = WorkbenchService(root)
    analytics = service.analytics(company="Example")
    assert analytics["inventory"] == {"fact_count": 1, "company_count": 1}
    assert analytics["facets"]["categories"] == {"Emissions": 1}
    schema = service.knowledge_schema()
    assert schema["categories"][0]["predicates"] == {"scope_1_emissions": 1}


def test_evidence_preview_rejects_unregistered_source(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    trusted = {
        "record_id": "fact-trusted",
        "subject": {"entity_label": "Example Plc"},
        "predicate": {"canonical_key": "water_withdrawal"},
        "value": "10",
        "evidence": [{"pdf_page": 1, "quote": "Water withdrawal 10"}],
    }
    (root / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl").write_text(
        json.dumps(trusted) + "\n", encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match="registered PDF path"):
        WorkbenchService(root).evidence_preview("fact-trusted", 0)


def test_job_fact_details_joins_projection_and_promotion_audits(tmp_path: Path) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    analysis = tmp_path / "data/workbench/jobs" / job["job_id"] / "analysis"
    analysis.mkdir()
    (analysis / "atomic_fact_candidates.jsonl").write_text(
        json.dumps({"record_id": "fact-abc", "value": 42}) + "\n", encoding="utf-8"
    )
    (analysis / "projection_audit_records.jsonl").write_text(
        json.dumps({"fact_record_id": "fact-abc", "status": "passed"}) + "\n",
        encoding="utf-8",
    )
    (analysis / "promotion_gate_records.jsonl").write_text(
        json.dumps({"fact_record_id": "fact-abc", "decision": "blocked"}) + "\n",
        encoding="utf-8",
    )
    (analysis / "failure_records.jsonl").write_text(
        json.dumps({"parent_fact_record_id": "fact-abc", "failure_signature": "SLOT"}) + "\n",
        encoding="utf-8",
    )
    (analysis / "repair_plan_records.jsonl").write_text(
        json.dumps({"fact_record_id": "fact-abc", "decision": "supervised_candidate"}) + "\n",
        encoding="utf-8",
    )
    (analysis / "repair_dispatch_records.jsonl").write_text(
        json.dumps({"fact_record_id": "fact-abc", "decision": "blocked"}) + "\n",
        encoding="utf-8",
    )
    (analysis / "repaired_fact_candidates.jsonl").write_text(
        json.dumps({"record_id": "fact-derived", "value": 42}) + "\n",
        encoding="utf-8",
    )
    (analysis / "repair_execution_records.jsonl").write_text(
        json.dumps(
            {
                "parent_fact_record_id": "fact-abc",
                "derived_fact_record_id": "fact-derived",
                "state": "postvalidation_passed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (analysis / "promotion_review_records.jsonl").write_text(
        json.dumps(
            {
                "review_id": "workbench-promotion-review-1",
                "fact_record_id": "fact-derived",
                "state": "pending_review",
                "version": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    details = service.job_fact_details(job["job_id"])
    assert details["matched"] == 1
    assert details["records"][0]["projection_audit"]["status"] == "passed"
    assert details["records"][0]["promotion_gate"]["decision"] == "blocked"
    assert details["records"][0]["failures"][0]["failure_signature"] == "SLOT"
    assert details["records"][0]["repair_plan"]["decision"] == "supervised_candidate"
    assert details["records"][0]["repair_dispatch"]["decision"] == "blocked"
    execution = details["records"][0]["repair_executions"][0]
    assert execution["state"] == "postvalidation_passed"
    assert execution["derived_fact"]["record_id"] == "fact-derived"
    assert execution["promotion_review"]["state"] == "pending_review"
    assert details["policy"]["trusted_layer_modified"] is False


def test_promotion_review_decision_is_job_local_and_versioned(tmp_path: Path) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    analysis = tmp_path / "data/workbench/jobs" / job["job_id"] / "analysis"
    analysis.mkdir()
    review = {
        "review_id": "workbench-promotion-review-1",
        "fact_record_id": "fact-derived",
        "state": "pending_review",
        "version": 1,
        "decision_history": [],
        "promotion_performed": False,
        "trusted_layer_modified": False,
    }
    (analysis / "promotion_review_records.jsonl").write_text(
        json.dumps(review) + "\n", encoding="utf-8"
    )

    updated = service.decide_promotion_review(
        job["job_id"],
        review["review_id"],
        {
            "decision": "request_more_evidence",
            "reviewer": "local reviewer",
            "rationale": "Scope evidence remains incomplete.",
            "expected_version": 1,
        },
    )
    assert updated["state"] == "evidence_required"
    assert updated["version"] == 2
    assert updated["promotion_performed"] is False
    assert service.promotion_reviews(job["job_id"])["records"][0] == updated
    assert (tmp_path / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl").read_text() == ""


def test_approved_review_creates_recoverable_staging_record(tmp_path: Path) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    analysis = tmp_path / "data/workbench/jobs" / job["job_id"] / "analysis"
    analysis.mkdir()
    fact = {
        "record_id": "fact-derived",
        "trust_tier": "C",
        "knowledge_status": "reference_candidate",
        "subject": {
            "entity_label": "Example Plc",
            "document_ids": ["source-a"],
            "document_metadata": [
                {
                    "source_id": "source-a",
                    "local_path": job["source"]["local_path"],
                    "sha256": job["source"]["sha256"],
                }
            ],
        },
        "predicate": {"canonical_key": "water.withdrawal"},
        "value": 100,
        "qualifiers": {
            "reference_period": 2025,
            "normalized_unit": "m3",
            "scope_boundary": "consolidated group",
        },
        "evidence": [
            {
                "source_id": "source-a",
                "quote": "Water withdrawal was 100 m3.",
                "coordinates": [1, 2, 3, 4],
                "role": "issuer disclosure",
            }
        ],
        "provenance": {"simulated": False},
        "promotion": {"eligible": False},
    }
    (analysis / "repaired_fact_candidates.jsonl").write_text(
        json.dumps(fact) + "\n", encoding="utf-8"
    )
    review = {
        "review_id": "workbench-promotion-review-1",
        "fact_record_id": "fact-derived",
        "state": "pending_review",
        "version": 1,
        "decision_history": [],
        "promotion_performed": False,
        "trusted_layer_modified": False,
    }
    (analysis / "promotion_review_records.jsonl").write_text(
        json.dumps(review) + "\n", encoding="utf-8"
    )

    service.decide_promotion_review(
        job["job_id"],
        review["review_id"],
        {
            "decision": "approve_for_promotion_staging",
            "reviewer": "local reviewer",
            "rationale": "The deterministic repair is valid.",
            "expected_version": 1,
        },
    )
    staging = service.promotion_staging(job["job_id"])["records"]
    assert len(staging) == 1
    assert staging[0]["state"] == "blocked_promotion_preconditions"
    assert "two_distinct_sources" in staging[0]["blocking_reasons"]
    assert staging[0]["promotion_performed"] is False
    assert (tmp_path / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl").read_text() == ""


def test_ready_staging_commit_and_withdraw_are_versioned_overlays(tmp_path: Path) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    analysis = tmp_path / "data/workbench/jobs" / job["job_id"] / "analysis"
    analysis.mkdir()
    staging = {
        "staging_id": "workbench-promotion-staging-ready",
        "review_id": "review-ready",
        "review_version": 2,
        "fact_record_id": "fact-ready",
        "state": "ready_for_tier_b_overlay_commit",
        "proposed_overlay": {
            "record_id": "fact-ready",
            "trust_tier": "B",
            "promotion": {"eligible": True, "committed": False},
        },
    }
    (analysis / "promotion_staging_records.jsonl").write_text(
        json.dumps(staging) + "\n", encoding="utf-8"
    )

    committed = service.commit_promotion_staging(
        job["job_id"],
        staging["staging_id"],
        {"actor": "reviewer", "rationale": "Independent support verified."},
    )
    overlay_id = committed["event"]["overlay_id"]
    assert committed["event"]["event_type"] == "overlay_committed"
    assert len(committed["active_overlays"]) == 1
    assert service.promotion_overlays()["active_count"] == 1
    assert (tmp_path / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl").read_text() == ""

    withdrawn = service.withdraw_promotion_overlay(
        overlay_id,
        {"actor": "reviewer", "rationale": "Source was superseded."},
    )
    assert withdrawn["event"]["event_type"] == "overlay_withdrawn"
    assert withdrawn["active_overlays"] == []
    ledger = service.promotion_overlays()
    assert ledger["active_count"] == 0
    assert ledger["event_count"] == 2
