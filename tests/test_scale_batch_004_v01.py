from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_mineru_resume_closes_all_target_pages_without_repeating_successes() -> None:
    first = load_json("data/results/scale_batch_004_mineru_RESUME01_summary.lock.json")
    second = load_json("data/results/scale_batch_004_mineru_RESUME02_summary.lock.json")
    assert first["complete_pages"] == 23
    assert first["failed_pages"] == 2
    assert second["complete_pages"] == 2
    assert second["failed_pages"] == 0
    assert {(item["document_id"], item["page"]) for item in second["records"]} == {
        ("KB-B004-PHILIPS-AR2025", 210),
        ("KB-B004-PHILIPS-AR2025", 221),
    }


def test_batch_four_atomic_candidates_fail_closed_at_tier_c() -> None:
    summary = load_json("data/results/scale_batch_004_atomic_validation.lock.json")
    assert summary["candidate_count"] == 8
    assert summary["coordinate_corroborated_count"] == 8
    assert summary["held_tier_c_count"] == 8
    assert summary["promoted_tier_b_count"] == 0


def test_two_gaps_are_resolved_as_non_promoted_candidates() -> None:
    summary = load_json("data/results/scale_batch_004_gap_repair.lock.json")
    facts = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_004_gap_repair_fact_records.jsonl"
    )
    assert summary["parent_gaps"] == 2
    assert summary["resolved_structured_table_filter_gaps"] == 2
    assert len(facts) == 2
    assert all(item["trust_tier"] == "C" for item in facts)
    assert all(item["promotion"]["eligible"] is False for item in facts)


def test_global_knowledge_bases_include_batch_four() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    assert manifest["counts"]["fact_records"] >= 1240
    assert manifest["counts"]["failure_records"] >= 111
    assert manifest["counts"]["failure_signatures"] >= 19
    assert len(load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")) >= 69
