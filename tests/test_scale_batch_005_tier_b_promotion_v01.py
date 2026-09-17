from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_batch_five_promotion_is_conservative_and_complete() -> None:
    summary = load_json("data/results/scale_batch_005_tier_b_promotion.lock.json")
    trusted = {item["record_id"]: item for item in load_jsonl(
        "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
    )}
    assert summary["reviewed"] == 32
    assert summary["newly_promoted_to_tier_b"] == 10
    assert summary["total_trusted_tier_b"] == 65
    assert set(summary["promotable_fact_ids"]) <= set(trusted)
    assert not set(summary["blocked_fact_ids"]) & set(trusted)


def test_prior_period_and_structurally_incomplete_cells_remain_blocked() -> None:
    summary = load_json("data/results/scale_batch_005_tier_b_promotion.lock.json")
    reasons = summary["blocked_by_reason"]
    assert len(reasons["malformed_row_header"]) == 3
    assert len(reasons["missing_explicit_unit_attachment"]) == 6
    assert len(reasons["prior_period_assurance_scope_not_established"]) == 13


def test_candidate_layer_remains_immutable_tier_c() -> None:
    candidates = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_005_atomic_fact_records.jsonl"
    )
    assert len(candidates) == 32
    assert all(item["trust_tier"] == "C" for item in candidates)
