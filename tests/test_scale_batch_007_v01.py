from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_batch_seven_sources_and_mineru_are_frozen_and_complete() -> None:
    acquisition = load_json("data/manifests/scale_batch_007_acquisition.lock.json")
    final = load_json("data/results/scale_batch_007_mineru_FINAL_summary.lock.json")
    assert acquisition["totals"] == {"documents": 3, "bytes": 52330371, "pages": 983}
    assert all(
        item["pdf_header_valid"] and item["pdfinfo_valid"] for item in acquisition["documents"]
    )
    assert final["complete_pages"] == 25
    assert final["failed_pages"] == 0
    assert final["post_completion_shutdown_recovered_pages"] == 6
    assert final["parent_failures_preserved"] is True


def test_batch_seven_gap_repair_and_atomic_validation_fail_closed() -> None:
    gap = load_json("data/results/scale_batch_007_gap_repair.lock.json")
    validation = load_json("data/results/scale_batch_007_atomic_validation.lock.json")
    repaired = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_007_gap_repair_fact_records.jsonl"
    )
    assert gap["parent_gaps"] == gap["resolved_html_table_filter_gaps"] == 3
    assert len(repaired) == 3
    assert all(item["trust_tier"] == "C" and not item["promotion"]["eligible"] for item in repaired)
    assert validation["candidate_count"] == 8
    assert validation["coordinate_corroborated_count"] == 6


def test_batch_seven_tier_b_promotion_is_six_dimension_fail_closed() -> None:
    summary = load_json("data/results/scale_batch_007_tier_b_promotion.lock.json")
    candidates = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_007_atomic_fact_records.jsonl"
    )
    trusted = {
        item["record_id"]: item
        for item in load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    }
    assert len(candidates) == 8
    assert all(item["trust_tier"] == "C" for item in candidates)
    assert summary["newly_promoted_to_tier_b"] == 3
    assert summary["total_trusted_tier_b"] == 72
    assert set(summary["promotable_fact_ids"]) <= set(trusted)
    assert set(summary["blocked_fact_ids"]).isdisjoint(trusted)
    assert len(summary["blocked_fact_ids"]) == 5


def test_batch_seven_global_kb_counts_include_increment() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    assert manifest["counts"]["fact_records"] >= 1431
    assert manifest["counts"]["failure_records"] >= 227
    assert manifest["counts"]["failure_signatures"] >= 20
    assert len(load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")) >= 72
