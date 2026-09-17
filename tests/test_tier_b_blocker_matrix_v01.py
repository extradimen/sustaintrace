import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_blocker_matrix_covers_every_blocked_tier_b_queue_item():
    queue = [
        json.loads(line)
        for line in (KB / "tier_b_adjudication_queue.jsonl").read_text().splitlines()
        if line
    ]
    blocked = {
        record["fact_record_id"]
        for record in queue
        if record["adjudication_status"] == "blocked_additional_qualification"
    }
    matrix = [
        json.loads(line)
        for line in (KB / "tier_b_blocker_matrix.jsonl").read_text().splitlines()
        if line
    ]
    schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-blocker-matrix-v0.1.schema.json").read_text()
    )
    assert len(matrix) == 53
    assert {record["fact_record_id"] for record in matrix} == blocked
    for record in matrix:
        validate(record, schema)
        assert record["execution_allowed"] is False


def test_matrix_never_treats_boundary_semantics_as_automatic():
    matrix = [
        json.loads(line)
        for line in (KB / "tier_b_blocker_matrix.jsonl").read_text().splitlines()
        if line
    ]
    boundary_blocked = [
        record
        for record in matrix
        if "BOUNDARY_ATTACHMENT_INCOMPLETE" in record["blocking_signatures"]
    ]
    assert boundary_blocked
    assert all(record["boundary_plan"] != "not_blocked" for record in boundary_blocked)
    assert all(record["execution_allowed"] is False for record in boundary_blocked)
