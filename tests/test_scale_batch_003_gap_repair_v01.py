from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_ten_parent_gaps_are_resolved_without_promotion() -> None:
    summary = load_json("data/results/scale_batch_003_gap_repair.lock.json")
    assert summary["parent_gaps"] == 10
    assert summary["resolved_structured_table_filter_gaps"] == 9
    assert summary["resolved_long_paragraph_filter_gaps"] == 1
    assert summary["new_fact_candidates"] == 10
    assert summary["promoted_tier_b"] == 0
    assert summary["policy"]["parent_results_overwritten"] is False


def test_repair_candidates_retain_exact_page_theme_and_tier() -> None:
    facts = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_003_gap_repair_fact_records.jsonl"
    )
    assert len(facts) == 10
    assert all(item["trust_tier"] == "C" for item in facts)
    assert all(item["promotion"]["eligible"] is False for item in facts)
    observed = {
        (
            item["evidence"][0]["source_id"],
            item["evidence"][0]["pdf_page"],
            item["predicate"]["raw_key"],
        )
        for item in facts
    }
    assert len(observed) == 10


def test_global_kb_can_grow_without_changing_trusted_tier_b() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    assert manifest["counts"]["fact_records"] >= 1185
    trusted = load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    assert len(trusted) >= 69
