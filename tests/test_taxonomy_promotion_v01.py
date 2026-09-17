import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_five_taxonomy_facts_promoted_but_unaudited_holcim_remains_blocked():
    promoted_ids = {
        item["fact_record_id"] for item in load("taxonomy_boundary_adjudications.jsonl")
    }
    trusted = {item["record_id"]: item for item in load("trusted_fact_records.jsonl")}
    blocked_ids = {
        item["fact_record_id"]
        for item in load("taxonomy_boundary_validations.jsonl")
        if item["validation_status"] == "blocked_explicitly_unaudited"
    }
    assert len(promoted_ids) == 5
    assert len(blocked_ids) == 2
    assert promoted_ids <= trusted.keys()
    assert blocked_ids.isdisjoint(trusted)
    assert len(trusted) >= 69
