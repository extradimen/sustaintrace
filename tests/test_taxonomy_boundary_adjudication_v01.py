import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_only_auditable_taxonomy_candidates_enter_derived_adjudication():
    records = [
        json.loads(line)
        for line in (KB / "taxonomy_boundary_adjudications.jsonl").read_text().splitlines()
        if line
    ]
    schema = json.loads(
        (ROOT / "schemas/knowledge/taxonomy-boundary-adjudication-v0.1.schema.json")
        .read_text()
    )
    assert len(records) == 5
    assert all(item["task_id"] != "P20-TAXONOMY-001" for item in records)
    for record in records:
        jsonschema.validate(record, schema)
        assert record["effective_blockers"] == []
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False
