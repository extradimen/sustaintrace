import copy
import json
from pathlib import Path

import jsonschema

from esg_reliable_discovery.repair_controller import validate_assurance_boundary_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_all_assurance_metadata_cases_pass_strict_source_boundary_validation():
    records = load_jsonl("assurance_boundary_validations.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/assurance-boundary-validation-v0.1.schema.json").read_text()
    )
    assert len(records) == 9
    for record in records:
        jsonschema.validate(record, schema)
        assert record["validation_status"] == "ready_for_supervised_execution"
        assert all(record["checks"].values())
        assert record["execution_performed"] is False
        assert record["promotion_performed"] is False


def test_missing_native_literal_fails_closed():
    case = next(
        item for item in load_jsonl("boundary_semantic_negative_cases.jsonl")
        if item["boundary_class"] == "assurance_scope_metadata"
    )
    fact = next(
        item for item in load_jsonl("fact_records.jsonl")
        if item["record_id"] == case["fact_record_id"]
    )
    binding = next(
        item for item in load_jsonl("source_native_field_bindings.jsonl")
        if item["fact_record_id"] == case["fact_record_id"]
    )
    resolution = next(
        item for item in load_jsonl("tier_b_blocker_resolutions.jsonl")
        if item["fact_record_id"] == case["fact_record_id"]
    )
    broken = copy.deepcopy(binding)
    for candidate in broken["candidates"]:
        candidate["context"] = "assurance context without the required literal"
    record = validate_assurance_boundary_case(
        case, fact, broken, resolution, ROOT, "test boundary"
    )
    assert record["validation_status"] == "not_ready"
    assert record["checks"]["literal_in_native_context"] is False
    assert record["execution_performed"] is False
    assert record["promotion_performed"] is False
