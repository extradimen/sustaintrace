import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_period_coordinate_adjudications_are_derived_and_reversible():
    records = load_jsonl(KB / "period_coordinate_adjudications.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/period-coordinate-adjudication-v0.1.schema.json").read_text()
    )
    assert len(records) == 9
    assert sum(r["coordinate_method"] == "table_header_column_position" for r in records) == 5
    assert sum(r["effective_status"] == "ready_for_independent_source_review" for r in records) == 3
    for record in records:
        validate(record, schema)
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False
        assert record["rollback"] == "delete_period_coordinate_adjudication"


def test_coordinate_adjudications_remove_only_period_blocker():
    matrix = {
        record["fact_record_id"]: record
        for record in load_jsonl(KB / "tier_b_blocker_matrix.jsonl")
    }
    prior_ids = {
        record["fact_record_id"]
        for record in load_jsonl(KB / "tier_b_blocker_resolutions.jsonl")
    }
    records = load_jsonl(KB / "period_coordinate_adjudications.jsonl")
    assert prior_ids.isdisjoint({record["fact_record_id"] for record in records})
    for record in records:
        original = matrix[record["fact_record_id"]]["blocking_signatures"]
        assert matrix[record["fact_record_id"]]["period_plan"] == (
            "explicit_predicate_year_requires_coordinate"
        )
        assert set(record["effective_blockers"]) == set(original) - {
            "PERIOD_ATTACHMENT_INCOMPLETE"
        }


def test_four_ambiguous_period_blockers_remain_unresolved():
    summary = json.loads(
        (KB / "period_coordinate_adjudication_summary.lock.json").read_text()
    )
    assert summary["remaining_period_blockers"] == 4
    assert summary["remaining_boundary_blockers"] == 43
    assert summary["source_fact_records_modified"] == 0
    assert summary["promotions_performed"] == 0
