import json
from pathlib import Path

from esg_reliable_discovery.repair_controller import (
    index_strategies,
    plan_boundary_repair,
    plan_repair,
)

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    catalog = json.loads(
        (ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json").read_text()
    )
    failures = [
        json.loads(line)
        for line in (ROOT / "data/knowledge_bases/v0.1/failure_records.jsonl")
        .read_text()
        .splitlines()
        if line
    ]
    return index_strategies(catalog), {item["task_id"]: item for item in failures}


def test_exact_handle_mismatch_is_only_an_automatic_candidate_in_operational_mode():
    strategies, failures = fixtures()
    operational = plan_repair(failures["P22-ENERGY-CALC-001"], strategies, mode="operational")
    locked = plan_repair(failures["P22-ENERGY-CALC-001"], strategies, mode="locked_evaluation")
    assert operational["decision"] == "automatic_candidate"
    assert operational["execution_performed"] is False
    assert locked["decision"] == "archive_only"


def test_unmapped_handle_and_executor_type_fail_closed():
    strategies, failures = fixtures()
    workforce = plan_repair(failures["P23-WORKFORCE-CALC-001"], strategies, mode="operational")
    assure = plan_repair(failures["P23-ASSURE-001"], strategies, mode="operational")
    assert workforce["decision"] == "blocked"
    assert assure["decision"] == "blocked"
    assert workforce["execution_performed"] is False


def test_semantic_boundary_plan_requires_enabled_validator_and_validation_record():
    ontology = json.loads(
        (ROOT / "configs/knowledge/boundary_semantic_ontology_v0.1.json").read_text()
    )
    validators = json.loads(
        (ROOT / "configs/knowledge/boundary_validator_catalog_v0.1.json").read_text()
    )
    case = json.loads(
        (ROOT / "data/knowledge_bases/v0.1/boundary_semantic_negative_cases.jsonl")
        .read_text()
        .splitlines()[0]
    )
    plan = plan_boundary_repair(case, ontology, validators)
    assert plan["decision"] == "blocked_validation_missing_or_failed"
    assert plan["execution_performed"] is False
    assert plan["promotion_performed"] is False


def test_semantic_boundary_plan_accepts_only_matching_ready_validation():
    ontology = json.loads(
        (ROOT / "configs/knowledge/boundary_semantic_ontology_v0.1.json").read_text()
    )
    validators = json.loads(
        (ROOT / "configs/knowledge/boundary_validator_catalog_v0.1.json").read_text()
    )
    case = json.loads(
        (ROOT / "data/knowledge_bases/v0.1/boundary_semantic_negative_cases.jsonl")
        .read_text()
        .splitlines()[0]
    )
    validation = next(
        json.loads(line)
        for line in (ROOT / "data/knowledge_bases/v0.1/assurance_boundary_validations.jsonl")
        .read_text()
        .splitlines()
        if json.loads(line)["case_id"] == case["case_id"]
    )
    plan = plan_boundary_repair(case, ontology, validators, validation)
    assert plan["decision"] == "supervised_candidate"
    assert plan["validation_id"] == validation["validation_id"]
    assert plan["execution_performed"] is False
    assert plan["promotion_performed"] is False
