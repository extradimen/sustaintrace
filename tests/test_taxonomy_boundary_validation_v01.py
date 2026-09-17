import copy
import json
from pathlib import Path

import jsonschema

from esg_reliable_discovery.repair_controller import validate_taxonomy_boundary_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_taxonomy_validation_separates_ready_and_explicitly_unaudited():
    records = load("taxonomy_boundary_validations.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/taxonomy-boundary-validation-v0.1.schema.json")
        .read_text()
    )
    assert len(records) == 7
    assert sum(r["validation_status"] == "ready_for_supervised_execution" for r in records) == 5
    blocked = [r for r in records if r["validation_status"] == "blocked_explicitly_unaudited"]
    assert len(blocked) == 2
    assert all(r["task_id"] == "P20-TAXONOMY-001" for r in blocked)
    for record in records:
        jsonschema.validate(record, schema)
        assert all(record["checks"].values())
        assert record["execution_performed"] is False
        assert record["promotion_performed"] is False


def test_missing_revision_relation_fails_closed_despite_literal_presence():
    fact_id = "fact-041d636e29fb4342bca2b91f"
    case = next(
        r
        for r in load("boundary_semantic_negative_cases.jsonl")
        if r["fact_record_id"] == fact_id
    )
    fact = next(r for r in load("fact_records.jsonl") if r["record_id"] == fact_id)
    binding = next(
        r
        for r in load("source_native_field_bindings.jsonl")
        if r["fact_record_id"] == fact_id
    )
    broken = copy.deepcopy(binding)
    for candidate in broken["candidates"]:
        candidate["context"] = candidate["context"].replace(
            "EUR 2.9 billion", "revised value removed"
        )
    spec = {
        "value_literal": "EUR 0.4 billion",
        "required_phrases": ["opex denominator", "EUR 0.4 billion", "EUR 2.9 billion"],
        "resolved_role": "original 2024 OpEx denominator before retrospective revision",
        "forbidden_roles": ["eligible", "aligned"],
        "value_kind": "amount",
        "unit": "EUR billion",
        "period": "2024 original",
        "evidence_mode": "native_narrative_relation",
        "audit_status": "pending_independent_scope_review",
    }
    broken_fact = copy.deepcopy(fact)
    broken_fact["evidence"] = [
        item for item in broken_fact["evidence"] if "2.9 billion" not in item["quote"]
    ]
    record = validate_taxonomy_boundary_case(case, broken_fact, broken, ROOT, spec)
    assert record["checks"]["literal_in_native_context"] is True
    assert record["checks"]["required_role_phrases_present"] is False
    assert record["validation_status"] == "not_ready"
