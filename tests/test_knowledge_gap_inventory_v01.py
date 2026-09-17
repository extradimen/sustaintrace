import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_generated_knowledge_gaps_are_unique_and_schema_valid_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
    if not path.exists():
        return
    schema = json.loads((ROOT / "schemas/knowledge/knowledge-gap-v0.1.schema.json").read_text())
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert len({item["gap_id"] for item in records}) == len(records)
    validator = Draft202012Validator(schema)
    assert not [error for item in records for error in validator.iter_errors(item)]
    assert all(item["execution_policy"] != "automatic" for item in records)
