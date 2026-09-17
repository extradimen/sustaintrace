import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_metric_component_facts_pass_six_dimensions_and_enter_overlay():
    ids = {
        item["fact_record_id"]
        for item in load("metric_component_boundary_adjudications.jsonl")
    }
    adjudications = {
        item["fact_record_id"]: item
        for item in load("tier_b_independent_adjudications.jsonl")
    }
    trusted = {item["record_id"]: item for item in load("trusted_fact_records.jsonl")}
    assert len(ids) == 6
    assert len(trusted) >= 69
    for fact_id in ids:
        assert all(
            item["status"] == "matched"
            for item in adjudications[fact_id]["dimensions"].values()
        )
        assert trusted[fact_id]["trust_tier"] == "B"
        assert trusted[fact_id]["provenance"]["simulated"] is False
