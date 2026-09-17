import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_period_repairs_are_derived_reversible_and_non_promoting_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/period_attachment_repairs.jsonl"
    if not path.exists():
        return
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert records
    assert all(item["execution_mode"] == "derived_layer_only" for item in records)
    assert all(item["fact_source_modified"] is False for item in records)
    assert all(item["promotion_performed"] is False for item in records)
    assert all(item["rollback"]["source_restoration_required"] is False for item in records)
