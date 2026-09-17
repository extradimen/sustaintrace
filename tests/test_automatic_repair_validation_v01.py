import json
from pathlib import Path

from esg_reliable_discovery.repair_controller import (
    index_strategies,
    plan_repair,
    validate_automatic_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_p22_exact_alias_candidate_prepares_rollback_without_execution():
    catalog = json.loads(
        (ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json").read_text()
    )
    strategies = index_strategies(catalog)
    failure = next(
        item
        for item in load_jsonl(ROOT / "data/knowledge_bases/v0.1/failure_records.jsonl")
        if item["task_id"] == "P22-ENERGY-CALC-001"
    )
    plan = plan_repair(failure, strategies, mode="operational")
    result = validate_automatic_candidate(
        plan, failure, strategies[failure["failure_signature"]], ROOT
    )
    assert result["validation_status"] == "ready_not_executed"
    assert result["execution_performed"] is False
    assert result["rollback_ledger"]["status"] == "prepared_not_executed"


def test_tampered_parent_hash_blocks_automatic_candidate():
    catalog = json.loads(
        (ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json").read_text()
    )
    strategies = index_strategies(catalog)
    failure = next(
        item
        for item in load_jsonl(ROOT / "data/knowledge_bases/v0.1/failure_records.jsonl")
        if item["task_id"] == "P22-ENERGY-CALC-001"
    )
    failure = json.loads(json.dumps(failure))
    failure["provenance"]["source_sha256"] = "0" * 64
    plan = plan_repair(failure, strategies, mode="operational")
    result = validate_automatic_candidate(
        plan, failure, strategies[failure["failure_signature"]], ROOT
    )
    assert result["validation_status"] == "not_ready"
    assert result["checks"]["failure_source_hash_valid"] is False
