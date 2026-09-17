from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_batch_ten_sources_and_mineru_are_frozen_and_complete() -> None:
    acquisition = load_json("data/manifests/scale_batch_010_acquisition.lock.json")
    final = load_json("data/results/scale_batch_010_mineru_FINAL_summary.lock.json")
    assert acquisition["totals"] == {"documents": 3, "bytes": 55755732, "pages": 1320}
    assert all(
        item["pdf_header_valid"] and item["pdfinfo_valid"] for item in acquisition["documents"]
    )
    assert final["complete_pages"] == 27
    assert final["failed_pages"] == 0
    assert final["parent_failures_preserved"] is True
    assert sum(item["selected_attempt"] == "RESUME01" for item in final["records"]) == 26
    assert sum(item["selected_attempt"] == "RESUME02" for item in final["records"]) == 1


def test_batch_ten_performance_baseline_is_separate_from_quality() -> None:
    performance = load_json("data/results/scale_batch_010_performance_baseline.lock.json")
    assert performance["whole_report_diagnostic"]["pdf_pages"] == 1320
    assert performance["whole_report_diagnostic"]["pages_per_second"] == 440.0
    assert performance["mineru"]["successful_target_pages"] == 27
    assert performance["mineru"]["successful_target_pages_per_hour"] > 80
    assert performance["mineru"]["checkpoint_reuse_pages"] == 26
    assert performance["policy"]["performance_separate_from_knowledge_quality"] is True


def test_batch_ten_atomic_projection_and_tier_b_promotion_fail_closed() -> None:
    validation = load_json("data/results/scale_batch_010_atomic_validation.lock.json")
    promotion = load_json("data/results/scale_batch_010_tier_b_promotion.lock.json")
    audit = load_json("data/results/scale_batch_010_native_coordinate_audit.lock.json")
    trusted = {
        item["record_id"]
        for item in load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    }
    assert validation["candidate_count"] == 17
    assert validation["table_graph_coordinate_exact_count"] == 17
    assert promotion["newly_promoted_to_tier_b"] == 3
    assert promotion["total_trusted_tier_b"] == 79
    assert set(promotion["promotable_fact_ids"]) <= trusted
    assert set(promotion["blocked_fact_ids"]).isdisjoint(trusted)
    assert audit["status"] == ("veolia_passed_puma_fail_closed_on_assurance_period_contradiction")
    assert all(audit["checks"].values())


def test_batch_ten_global_kb_counts_are_preserved_as_monotonic_baseline() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    milestone = load_json("data/results/scale_batch_010_milestone_audit.lock.json")
    assert milestone["global_knowledge_bases"]["fact_records"] == 1603
    assert milestone["global_knowledge_bases"]["failure_records"] == 290
    assert manifest["counts"]["fact_records"] >= 1603
    assert manifest["counts"]["failure_records"] >= 290
    assert manifest["counts"]["failure_signatures"] >= 21
    assert len(load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")) >= 79
