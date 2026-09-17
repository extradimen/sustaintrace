from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text().splitlines()
        if line
    ]


def test_gap_repair_resume_completed_only_referred_pages() -> None:
    summary = load_json(
        "data/results/scale_batch_002_gap_repair_mineru_RESUME01_summary.lock.json"
    )
    assert summary["complete_pages"] == 2
    assert summary["failed_pages"] == 0
    assert {item["page"] for item in summary["records"]} == {79, 80}


def test_four_parent_gaps_are_resolved_without_promotion() -> None:
    summary = load_json("data/results/scale_batch_002_gap_repair.lock.json")
    assert summary["parent_gaps"] == 4
    assert summary["resolved_structured_table_filter_gaps"] == 3
    assert summary["resolved_index_to_disclosure_page_gaps"] == 1
    assert summary["new_fact_candidates"] == 12
    assert summary["promoted_tier_b"] == 0
    assert summary["policy"]["parent_results_overwritten"] is False


def test_repair_candidates_retain_source_page_and_tier_c() -> None:
    facts = load_jsonl(
        "data/knowledge_bases/v0.1/increments/"
        "scale_batch_002_gap_repair_fact_records.jsonl"
    )
    assert len(facts) == 12
    assert all(item["trust_tier"] == "C" for item in facts)
    assert all(item["promotion"]["eligible"] is False for item in facts)
    pages = {item["evidence"][0]["pdf_page"] for item in facts}
    assert pages == {26, 53, 55, 79, 80}


def test_global_kb_contains_repair_increments() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    assert manifest["counts"]["fact_records"] >= 1144
    assert manifest["counts"]["failure_records"] >= 74
    assert manifest["counts"]["failure_signatures"] >= 17
