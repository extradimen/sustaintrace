import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_explicit_boundary_adjudications_are_derived_and_reversible():
    records = load_jsonl(KB / "boundary_coordinate_adjudications.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/boundary-coordinate-adjudication-v0.1.schema.json").read_text()
    )
    assert len(records) == 15
    assert all(r["effective_status"] == "ready_for_independent_source_review" for r in records)
    for record in records:
        validate(record, schema)
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False
        assert record["rollback"] == "delete_boundary_coordinate_adjudication"


def test_boundary_resolution_preserves_other_unresolved_signatures():
    matrix = {
        r["fact_record_id"]: r for r in load_jsonl(KB / "tier_b_blocker_matrix.jsonl")
    }
    period_ids = {
        r["fact_record_id"] for r in load_jsonl(KB / "tier_b_blocker_resolutions.jsonl")
    } | {
        r["fact_record_id"] for r in load_jsonl(KB / "period_coordinate_adjudications.jsonl")
    }
    for record in load_jsonl(KB / "boundary_coordinate_adjudications.jsonl"):
        source = matrix[record["fact_record_id"]]
        expected = set(source["blocking_signatures"]) - {"BOUNDARY_ATTACHMENT_INCOMPLETE"}
        if record["fact_record_id"] in period_ids:
            expected.discard("PERIOD_ATTACHMENT_INCOMPLETE")
        assert set(record["effective_blockers"]) == expected


def test_semantic_boundary_items_remain_blocked():
    summary = json.loads(
        (KB / "boundary_coordinate_adjudication_summary.lock.json").read_text()
    )
    assert summary["remaining_boundary_blockers"] == 28
    assert summary["source_fact_records_modified"] == 0
    assert summary["promotions_performed"] == 0
