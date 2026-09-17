import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_six_dimension_adjudications_are_complete_and_fail_closed():
    records = load_jsonl(KB / "tier_b_independent_adjudications.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-independent-adjudication-v0.1.schema.json").read_text()
    )
    assert len(records) >= 72
    for record in records:
        validate(record, schema)
        assert set(record["dimensions"]) == {
            "entity",
            "metric",
            "period",
            "unit",
            "scope_boundary",
            "value",
        }
        assert all(item["status"] == "matched" for item in record["dimensions"].values())
        assert record["promotion_decision"]["eligible"] is True


def test_trusted_facts_are_append_only_overlays():
    source = {record["record_id"]: record for record in load_jsonl(KB / "fact_records.jsonl")}
    trusted = load_jsonl(KB / "trusted_fact_records.jsonl")
    assert len(trusted) >= 72
    assert len(trusted) == len(load_jsonl(KB / "tier_b_independent_adjudications.jsonl"))
    for record in trusted:
        assert source[record["record_id"]]["trust_tier"] == "C"
        assert source[record["record_id"]]["promotion"]["eligible"] is False
        assert record["trust_tier"] == "B"
        assert record["knowledge_status"] == "promoted_validated_fact"
        assert record["promotion"]["eligible"] is True
        assert record["provenance"]["simulated"] is False
