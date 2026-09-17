import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]


def test_generated_tier_b_queue_is_fail_closed_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/tier_b_adjudication_queue.jsonl"
    if not path.exists():
        return
    schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-adjudication-queue-v0.1.schema.json").read_text()
    )
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert records
    assert all(item["promotion_eligible"] is False for item in records)
    assert all(item["independent_source_present"] is False for item in records)
    assert all(item["source_native_status"] == "unique_context_binding" for item in records)
    assert any(
        item["adjudication_status"] == "ready_for_independent_source_review" for item in records
    )
    for item in records:
        validate(item, schema)
