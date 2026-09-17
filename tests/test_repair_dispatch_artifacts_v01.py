import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_current_automatic_candidates_fail_closed_before_execution():
    schema = json.loads(
        (ROOT / "schemas/knowledge/repair-dispatch-decision-v0.1.schema.json").read_text()
    )
    decisions = [
        json.loads(line)
        for line in (KB / "repair_dispatch_decisions.jsonl").read_text().splitlines()
        if line
    ]
    assert len(decisions) == 4
    for decision in decisions:
        validate(decision, schema)
        assert decision["decision"] == "blocked"
        assert decision["execution_started"] is False
        assert decision["execution_state"] is None
        assert "frozen_execution_contract_missing" in decision["blocking_reasons"]


def test_dispatch_summary_records_no_silent_execution():
    summary = json.loads((KB / "repair_dispatch_summary.lock.json").read_text())
    assert summary["automatic_candidates"] == 4
    assert summary["ready_for_execution"] == 0
    assert summary["blocked"] == 4
    assert summary["execution_started"] == 0
    assert summary["locked_experiments_modified_or_rescored"] is False
