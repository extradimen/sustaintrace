import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_target_performance_adjudication_is_fail_closed_and_reproducible():
    records = [
        json.loads(line)
        for line in (KB / "target_performance_derived_adjudications.jsonl").read_text().splitlines()
        if line
    ]
    assert len(records) == 4
    assert sum(item["decision"] == "ready_for_tier_b_promotion" for item in records) == 1
    ready = next(item for item in records if item["decision"] == "ready_for_tier_b_promotion")
    assert ready["predicate"] == "issuer_reduction_percent"
    assert ready["checks"]["deterministic_recalculation"]["passed"] is True
    assert ready["checks"]["deterministic_recalculation"]["rounded_absolute_percent"] == 14
    blocked = {item["predicate"]: item for item in records if item is not ready}
    assert "target_2030_absolute_reduction_percent" in blocked
    assert "target_2045_absolute_reduction_percent" in blocked
    assert "reduction_from_2020_baseline_percent" in blocked
    schema = json.loads(
        (
            ROOT / "schemas/knowledge/target-performance-derived-adjudication-v0.1.schema.json"
        ).read_text()
    )
    for record in records:
        jsonschema.validate(record, schema)
