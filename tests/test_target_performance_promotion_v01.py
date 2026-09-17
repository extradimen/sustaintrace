import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_only_independently_reproduced_target_performance_fact_is_promoted():
    derived = load("target_performance_derived_adjudications.jsonl")
    trusted = {item["record_id"]: item for item in load("trusted_fact_records.jsonl")}
    ready = [item for item in derived if item["decision"] == "ready_for_tier_b_promotion"]
    blocked = [
        item for item in derived if item["decision"] == "blocked_independent_evidence_incomplete"
    ]
    assert len(ready) == 1
    assert len(blocked) == 3
    fact = trusted[ready[0]["fact_record_id"]]
    assert fact["value"] == 14
    assert fact["qualifiers"]["reference_period"] == 2024
    assert (
        fact["qualifiers"]["value_origin"]
        == "deterministic_recalculation_from_independently_assured_operands"
    )
    assert all(item["fact_record_id"] not in trusted for item in blocked)


def test_promotion_preserves_candidate_layer():
    candidates = {item["record_id"]: item for item in load("fact_records.jsonl")}
    target_ids = {
        item["fact_record_id"] for item in load("target_performance_derived_adjudications.jsonl")
    }
    assert all(candidates[fact_id]["trust_tier"] == "C" for fact_id in target_ids)
    assert all(candidates[fact_id]["promotion"]["eligible"] is False for fact_id in target_ids)
