import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_closure_replay_promotes_only_after_postvalidation_and_rolls_back_failures():
    states = load("repair_execution_states.jsonl")
    events = load("repair_execution_events.jsonl")
    failures = load("repair_execution_regression_failures.jsonl")
    assert sum(item["state"] == "promoted" for item in states) == 1
    assert sum(item["state"] == "rolled_back" for item in states) == 2
    assert sum(item["state"] == "blocked_preflight" for item in states) == 1
    promoted = next(item for item in states if item["state"] == "promoted")
    promotion_events = [item for item in events if item["execution_id"] == promoted["execution_id"]]
    assert [item["to_state"] for item in promotion_events] == [
        "preflight_passed",
        "executed",
        "postvalidation_passed",
        "promoted",
    ]
    assert len(failures) == 3
    assert all(item["detected"] for item in failures)
    assert all(not item["source_artifacts_modified"] for item in failures)


def test_hash_and_invariant_failures_never_promote():
    states = {item["execution_id"]: item for item in load("repair_execution_states.jsonl")}
    failures = load("repair_execution_regression_failures.jsonl")
    for failure in failures:
        state = states[failure["execution_id"]]
        assert state["promotion_performed"] is False
        if failure["failed_gate"] == "postvalidation":
            assert state["state"] == "rolled_back"
            assert state["rollback_performed"] is True
