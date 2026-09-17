from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_batch_four_promotes_only_exactly_assured_circular_metrics() -> None:
    summary = load_json("data/results/scale_batch_004_tier_b_promotion.lock.json")
    trusted = {
        item["record_id"]: item
        for item in load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    }
    assert summary["reviewed"] == 8
    assert summary["newly_promoted_to_tier_b"] == 5
    assert summary["total_trusted_tier_b"] == 55
    assert set(summary["promotable_fact_ids"]) <= set(trusted)
    assert not set(summary["blocked_fact_ids"]) & set(trusted)
    assert all(trusted[fact_id]["trust_tier"] == "B" for fact_id in summary["promotable_fact_ids"])


def test_target_value_is_not_misrepresented_as_achievement() -> None:
    trusted = {
        item["record_id"]: item
        for item in load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    }
    target = trusted["fact-4f6b615deb687ed51454ed9e"]
    assert target["qualifiers"]["period_literal"] == "Target 2025"
    assert "target disclosure" in target["qualifiers"]["scope_boundary"]
    assert target["qualifiers"]["answer_status"] == "verified"


def test_batch_four_candidate_layer_remains_immutable_tier_c() -> None:
    candidates = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_004_atomic_fact_records.jsonl"
    )
    assert len(candidates) == 8
    assert all(item["trust_tier"] == "C" for item in candidates)
    assert all(item["promotion"]["eligible"] is False for item in candidates)
