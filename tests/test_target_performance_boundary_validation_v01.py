import copy
import json
from pathlib import Path

import jsonschema

from esg_reliable_discovery.repair_controller import validate_target_performance_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def context():
    return "\n".join(
        candidate.get("context", "")
        for binding in load("source_native_field_bindings.jsonl")
        if binding.get("task_id", "").startswith("P23-")
        for candidate in binding.get("candidates", [])
    )


def spec_for(fact_id):
    specs = {
        "fact-f216f8cbb3e2c3cc919d7b20": {
            "expected_value": 80,
            "claim_role": "target",
            "metric": "absolute greenhouse gas emissions reduction",
            "unit": "percent",
            "target_year": 2030,
            "performance_year": None,
            "baseline_or_comparator": 2020,
            "baseline_relation": "from a 2020 baseline",
            "scope_boundary": "all scopes; remaining 20% addressed through nature-based solutions",
            "resolved_relation": (
                "80% absolute reduction by 2030 from a 2020 baseline across all scopes"
            ),
            "required_phrases": [
                "80% absolute reduction",
                "2020 baseline",
                "all scopes",
                "remaining 20%",
                "by 2030",
            ],
            "metric_scope_markers": ["greenhouse gas emissions", "all scopes"],
            "forbidden_relation_phrases": ["2045", "14% compared with 2024"],
            "audit_status": "pending_independent_scope_review",
        },
        "fact-13f596f084681dd4cdf45571": {
            "expected_value": 14,
            "claim_role": "achieved_performance",
            "metric": "Scope 1 and 2 carbon emissions reduction",
            "unit": "percent",
            "target_year": None,
            "performance_year": 2025,
            "baseline_or_comparator": 2024,
            "baseline_relation": "compared with 2024",
            "scope_boundary": "Scope 1 and Scope 2 carbon emissions",
            "resolved_relation": "2025 Scope 1 and 2 emissions were 14% lower than 2024",
            "required_phrases": [
                "in 2025",
                "scope 1 & 2",
                "by 14%",
                "compared with 2024",
            ],
            "metric_scope_markers": ["scope 1 & 2", "carbon emissions"],
            "forbidden_relation_phrases": ["45%", "2020 baseline", "target"],
            "audit_status": "pending_independent_scope_review",
        },
    }
    return {**specs[fact_id], "supporting_context": context()}


def test_four_target_and_performance_relations_are_separated():
    records = load("target_performance_boundary_validations.jsonl")
    schema = json.loads(
        (
            ROOT / "schemas/knowledge/target-performance-boundary-validation-v0.1.schema.json"
        ).read_text()
    )
    assert len(records) == 4
    assert sum(item["resolved_claim"]["claim_role"] == "target" for item in records) == 2
    assert (
        sum(item["resolved_claim"]["claim_role"] == "achieved_performance" for item in records) == 2
    )
    for record in records:
        jsonschema.validate(record, schema)
        assert all(record["checks"].values())
        assert record["validation_status"] == "ready_for_supervised_execution"


def test_missing_target_baseline_fails_closed_despite_percentage_literal():
    fact_id = "fact-f216f8cbb3e2c3cc919d7b20"
    case = next(
        item
        for item in load("boundary_semantic_negative_cases.jsonl")
        if item["fact_record_id"] == fact_id
    )
    fact = next(item for item in load("fact_records.jsonl") if item["record_id"] == fact_id)
    binding = next(
        item
        for item in load("source_native_field_bindings.jsonl")
        if item["fact_record_id"] == fact_id
    )
    spec = spec_for(fact_id)
    broken_fact = copy.deepcopy(fact)
    broken_binding = copy.deepcopy(binding)
    for evidence in broken_fact["evidence"]:
        evidence["quote"] = evidence["quote"].replace("2020 baseline", "baseline omitted")
    for candidate in broken_binding["candidates"]:
        candidate["context"] = candidate["context"].replace("2020 baseline", "baseline omitted")
    spec["supporting_context"] = spec["supporting_context"].replace(
        "2020 baseline", "baseline omitted"
    )
    record = validate_target_performance_case(case, broken_fact, broken_binding, ROOT, spec)
    assert record["checks"]["literal_in_native_context"] is True
    assert record["checks"]["required_relation_phrases_present"] is False
    assert record["validation_status"] == "not_ready"


def test_wrong_performance_comparator_fails_closed():
    fact_id = "fact-13f596f084681dd4cdf45571"
    case = next(
        item
        for item in load("boundary_semantic_negative_cases.jsonl")
        if item["fact_record_id"] == fact_id
    )
    fact = next(item for item in load("fact_records.jsonl") if item["record_id"] == fact_id)
    binding = next(
        item
        for item in load("source_native_field_bindings.jsonl")
        if item["fact_record_id"] == fact_id
    )
    spec = {**spec_for(fact_id), "baseline_or_comparator": 2023}
    record = validate_target_performance_case(case, fact, binding, ROOT, spec)
    assert record["checks"]["literal_in_native_context"] is True
    assert record["checks"]["baseline_or_comparator_bound"] is False
    assert record["validation_status"] == "not_ready"
