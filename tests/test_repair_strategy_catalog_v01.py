import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_repair_strategies_validate_and_cover_observed_signatures():
    catalog = json.loads(
        (ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json").read_text()
    )
    schema = json.loads(
        (ROOT / "schemas/knowledge/repair-strategy-v0.1.schema.json").read_text()
    )
    validator = Draft202012Validator(schema)
    for strategy in catalog["strategies"]:
        assert not list(validator.iter_errors(strategy))

    observed = {
        record["failure_signature"]
        for record in load_jsonl(ROOT / "data/knowledge_bases/v0.1/failure_records.jsonl")
    }
    covered = {
        signature
        for strategy in catalog["strategies"]
        for signature in strategy["target_signatures"]
    }
    assert observed <= covered


def test_automatic_strategies_are_low_risk_and_have_rollback_gates():
    catalog = json.loads(
        (ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json").read_text()
    )
    automatic = [
        strategy
        for strategy in catalog["strategies"]
        if strategy["execution_policy"] == "automatic"
    ]
    assert automatic
    for strategy in automatic:
        assert strategy["risk_level"] == "low"
        assert strategy["validation_gates"]
        assert strategy["rollback"]
