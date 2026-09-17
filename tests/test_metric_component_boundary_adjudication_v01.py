import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_metric_component_adjudications_are_derived_and_ready_for_review():
    records = [
        json.loads(line)
        for line in (KB / "metric_component_boundary_adjudications.jsonl")
        .read_text()
        .splitlines()
        if line
    ]
    schema = json.loads(
        (ROOT / "schemas/knowledge/metric-component-boundary-adjudication-v0.1.schema.json")
        .read_text()
    )
    assert len(records) == 6
    for record in records:
        jsonschema.validate(record, schema)
        assert record["effective_blockers"] == []
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False
