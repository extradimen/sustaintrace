import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_two_population_facts_pass_adjudication_and_enter_tier_b_overlay():
    boundary = load("organizational_population_boundary_adjudications.jsonl")
    trusted = load("trusted_fact_records.jsonl")
    independent = load("tier_b_independent_adjudications.jsonl")
    boundary_ids = {item["fact_record_id"] for item in boundary}
    trusted_ids = {item["record_id"] for item in trusted}
    reviews = {item["fact_record_id"]: item for item in independent}
    assert len(boundary_ids) == 2
    assert boundary_ids <= trusted_ids
    assert boundary_ids <= reviews.keys()
    for fact_id in boundary_ids:
        assert reviews[fact_id]["promotion_decision"]["eligible"] is True
        assert all(item["status"] == "matched" for item in reviews[fact_id]["dimensions"].values())
    schema = json.loads((ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text())
    for fact in trusted:
        jsonschema.validate(fact, schema)


def test_population_promotion_preserves_original_candidate_layer():
    candidates = {item["record_id"]: item for item in load("fact_records.jsonl")}
    boundary_ids = {
        item["fact_record_id"]
        for item in load("organizational_population_boundary_adjudications.jsonl")
    }
    assert all(candidates[fact_id]["trust_tier"] == "C" for fact_id in boundary_ids)
    assert all(candidates[fact_id]["promotion"]["eligible"] is False for fact_id in boundary_ids)
