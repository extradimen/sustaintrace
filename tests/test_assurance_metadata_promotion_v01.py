import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_assurance_metadata_passes_six_dimensions_and_is_added_to_tier_b_overlay():
    boundary_ids = {
        item["fact_record_id"] for item in load("assurance_boundary_adjudications.jsonl")
    }
    adjudications = {
        item["fact_record_id"]: item
        for item in load("tier_b_independent_adjudications.jsonl")
    }
    trusted = {item["record_id"]: item for item in load("trusted_fact_records.jsonl")}
    assert len(boundary_ids) == 9
    assert len(trusted) >= 69
    for fact_id in boundary_ids:
        assert set(adjudications[fact_id]["dimensions"]) == {
            "entity", "metric", "period", "unit", "scope_boundary", "value"
        }
        assert all(
            value["status"] == "matched"
            for value in adjudications[fact_id]["dimensions"].values()
        )
        assert trusted[fact_id]["trust_tier"] == "B"
        assert trusted[fact_id]["provenance"]["simulated"] is False
