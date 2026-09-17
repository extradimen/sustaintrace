import copy
import json
from pathlib import Path

import jsonschema

from esg_reliable_discovery.repair_controller import validate_organizational_population_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def spec(scope_role):
    supporting_context = "\n".join(
        candidate.get("context", "")
        for binding in load("source_native_field_bindings.jsonl")
        if binding.get("task_id") == "P20-WORKFORCE-001"
        for candidate in binding.get("candidates", [])
    )
    return {
        "global_headcount": 46055,
        "covered_headcount": 43875,
        "excluded_headcount": 2180,
        "permanent_employees": 40590,
        "temporary_employees": 3285,
        "scope_role": scope_role,
        "audit_status": "pending_independent_scope_review",
        "supporting_context": supporting_context,
    }


def test_population_validation_reconciles_both_population_roles():
    records = load("organizational_population_boundary_validations.jsonl")
    schema = json.loads(
        (
            ROOT
            / "schemas/knowledge/organizational-population-boundary-validation-v0.1.schema.json"
        ).read_text()
    )
    assert len(records) == 2
    assert {record["predicate"] for record in records} == {
        "difference_headcount",
        "global_headcount",
    }
    for record in records:
        jsonschema.validate(record, schema)
        assert all(record["checks"].values())
        assert record["validation_status"] == "ready_for_supervised_execution"
        population = record["resolved_population"]
        assert (
            population["covered_headcount"] + population["excluded_headcount"]
            == population["global_headcount"]
        )
        assert (
            population["permanent_employees"] + population["temporary_employees"]
            == population["covered_headcount"]
        )


def test_missing_acquisition_exclusion_fails_closed():
    fact_id = "fact-6062d3c7c5e37b393ab17a6f"
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
    broken_fact = copy.deepcopy(fact)
    broken_binding = copy.deepcopy(binding)
    for evidence in broken_fact["evidence"]:
        evidence["quote"] = evidence["quote"].replace(
            "newly acquired entities", "unspecified entities"
        )
    for candidate in broken_binding["candidates"]:
        candidate["context"] = candidate["context"].replace(
            "newly acquired entities", "unspecified entities"
        )
    broken_spec = spec("hr_system_covered_employee_population_gap")
    broken_spec["supporting_context"] = broken_spec["supporting_context"].replace(
        "newly acquired entities", "unspecified entities"
    )
    record = validate_organizational_population_case(
        case,
        broken_fact,
        broken_binding,
        ROOT,
        broken_spec,
    )
    assert record["checks"]["excluded_population_present"] is True
    assert record["checks"]["new_acquisition_exclusion_explicit"] is False
    assert record["validation_status"] == "not_ready"


def test_arithmetic_mismatch_fails_closed_even_when_literals_exist():
    fact_id = "fact-e006f9b4f707f3abf5c2059c"
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
    broken_spec = spec("global_group_employee_population")
    broken_spec["covered_headcount"] = 43874
    record = validate_organizational_population_case(case, fact, binding, ROOT, broken_spec)
    assert record["checks"]["global_employee_population_present"] is True
    assert record["checks"]["excluded_population_reconciles"] is False
    assert record["validation_status"] == "not_ready"
