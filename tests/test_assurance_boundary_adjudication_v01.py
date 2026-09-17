import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_nine_validated_assurance_boundaries_are_derived_only():
    records = [
        json.loads(line)
        for line in (KB / "assurance_boundary_adjudications.jsonl").read_text().splitlines()
        if line
    ]
    schema = json.loads(
        (ROOT / "schemas/knowledge/assurance-boundary-adjudication-v0.1.schema.json")
        .read_text()
    )
    assert len(records) == 9
    assert len({item["fact_record_id"] for item in records}) == 9
    for record in records:
        jsonschema.validate(record, schema)
        assert record["effective_blockers"] == []
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False
