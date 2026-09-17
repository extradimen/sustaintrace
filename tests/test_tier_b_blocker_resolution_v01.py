import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_period_resolutions_are_derived_and_reversible():
    records = load_jsonl(KB / "tier_b_blocker_resolutions.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-blocker-resolution-v0.1.schema.json").read_text()
    )
    assert len(records) == 14
    assert sum(record["resolution_type"] == "exact_source_label" for record in records) == 3
    assert (
        sum(
            record["resolution_type"] == "not_applicable_non_temporal_field"
            for record in records
        )
        == 11
    )
    for record in records:
        validate(record, schema)
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False
        assert record["rollback"] == "delete_derived_resolution_record"


def test_resolutions_remove_only_the_period_blocker():
    matrix = {
        record["fact_record_id"]: record
        for record in load_jsonl(KB / "tier_b_blocker_matrix.jsonl")
    }
    records = load_jsonl(KB / "tier_b_blocker_resolutions.jsonl")
    for record in records:
        original = matrix[record["fact_record_id"]]["blocking_signatures"]
        assert "PERIOD_ATTACHMENT_INCOMPLETE" in original
        assert "PERIOD_ATTACHMENT_INCOMPLETE" not in record["effective_blockers"]
        assert set(record["effective_blockers"]) == set(original) - {
            "PERIOD_ATTACHMENT_INCOMPLETE"
        }
