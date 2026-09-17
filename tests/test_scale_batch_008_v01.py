from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_batch_eight_sources_and_mineru_are_frozen_and_complete() -> None:
    acquisition = load_json("data/manifests/scale_batch_008_acquisition.lock.json")
    final = load_json("data/results/scale_batch_008_mineru_FINAL_summary.lock.json")
    assert acquisition["totals"] == {"documents": 3, "bytes": 25920998, "pages": 431}
    assert all(
        item["pdf_header_valid"] and item["pdfinfo_valid"] for item in acquisition["documents"]
    )
    assert final["complete_pages"] == 26
    assert final["failed_pages"] == 0
    assert final["post_completion_shutdown_recovered_pages"] == 7
    assert final["parent_failures_preserved"] is True


def test_batch_eight_gap_repair_and_atomic_validation_fail_closed() -> None:
    gap = load_json("data/results/scale_batch_008_gap_repair.lock.json")
    validation = load_json("data/results/scale_batch_008_atomic_validation.lock.json")
    repaired = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_008_gap_repair_fact_records.jsonl"
    )
    assert gap["parent_gaps"] == gap["resolved_html_table_filter_gaps"] == 1
    assert len(repaired) == 1
    assert repaired[0]["trust_tier"] == "C"
    assert repaired[0]["promotion"]["eligible"] is False
    assert validation["candidate_count"] == 2
    assert validation["table_graph_coordinate_exact_count"] == 2


def test_batch_eight_tier_b_promotion_excludes_comparative_period() -> None:
    summary = load_json("data/results/scale_batch_008_tier_b_promotion.lock.json")
    audit = load_json("data/results/scale_batch_008_native_coordinate_audit.lock.json")
    trusted = {
        item["record_id"]: item
        for item in load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    }
    assert audit["status"] == "passed"
    assert all(audit["checks"].values())
    assert summary["newly_promoted_to_tier_b"] == 1
    assert summary["total_trusted_tier_b"] == 73
    assert set(summary["promotable_fact_ids"]) <= set(trusted)
    assert set(summary["blocked_fact_ids"]).isdisjoint(trusted)


def test_batch_eight_global_kb_counts_include_increment() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    assert manifest["counts"]["fact_records"] >= 1482
    assert manifest["counts"]["failure_records"] >= 258
    assert manifest["counts"]["failure_signatures"] >= 20
    assert len(load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")) >= 73
