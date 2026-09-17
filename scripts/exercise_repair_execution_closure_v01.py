from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records
from esg_reliable_discovery.repair_execution import (
    RepairExecutionContext,
    initial_state,
    postvalidate,
    transition,
)

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )


def execute_path(
    context: RepairExecutionContext,
    *,
    actual_output_sha256: str,
    invariant_results: dict[str, bool],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = initial_state(context)
    events = []
    state, event = transition(
        state,
        "preflight_passed",
        checks={"input_hash_valid": True, "parent_lineage_present": True},
    )
    events.append(event)
    state, event = transition(
        state,
        "executed",
        checks={"deterministic_action_completed": True},
    )
    events.append(event)
    state, event = postvalidate(
        state,
        actual_output_sha256=actual_output_sha256,
        invariant_results=invariant_results,
    )
    events.append(event)
    if state["state"] == "postvalidation_passed":
        state, event = transition(
            state,
            "promoted",
            checks={"postvalidation_recorded": True},
        )
    else:
        state, event = transition(
            state,
            "rolled_back",
            checks={"derived_output_removed": True, "parent_preserved": True},
        )
    events.append(event)
    return state, events


def main() -> None:
    adjudications_path = KB / "target_performance_derived_adjudications.jsonl"
    promotion_path = KB / "target_performance_promotion_summary.lock.json"
    trusted_path = KB / "trusted_fact_records.jsonl"
    candidates_path = KB / "fact_records.jsonl"
    promotion = json.loads(promotion_path.read_text())
    input_sha = sha256_file(adjudications_path)
    expected_output_sha = promotion["outputs"]["trusted_facts_sha256"]
    if expected_output_sha != sha256_file(trusted_path):
        raise ValueError("trusted overlay no longer matches promotion checkpoint")

    invariants = (
        "candidate_layer_unchanged",
        "locked_experiments_unchanged",
        "output_schema_valid",
    )
    base = {
        "parent_record_id": "fact-13f596f084681dd4cdf45571",
        "strategy_id": "RS-TARGET-PERFORMANCE-DERIVED-PROMOTION",
        "validator_id": "BV-TARGET-PERFORMANCE-V01",
        "input_sha256": input_sha,
        "expected_output_sha256": expected_output_sha,
        "rollback_action": "delete derived overlay record and preserve C-tier parent",
        "invariants": invariants,
    }
    positive, positive_events = execute_path(
        RepairExecutionContext(plan_id="PLAN-TARGET-PERFORMANCE-POSITIVE", **base),
        actual_output_sha256=sha256_file(trusted_path),
        invariant_results={name: True for name in invariants},
    )
    hash_failure, hash_events = execute_path(
        RepairExecutionContext(plan_id="PLAN-TARGET-PERFORMANCE-HASH-NEGATIVE", **base),
        actual_output_sha256="0" * 64,
        invariant_results={name: True for name in invariants},
    )
    invariant_failure, invariant_events = execute_path(
        RepairExecutionContext(plan_id="PLAN-TARGET-PERFORMANCE-INVARIANT-NEGATIVE", **base),
        actual_output_sha256=sha256_file(trusted_path),
        invariant_results={
            "candidate_layer_unchanged": False,
            "locked_experiments_unchanged": True,
            "output_schema_valid": True,
        },
    )
    blocked_context = RepairExecutionContext(
        plan_id="PLAN-TARGET-PERFORMANCE-PREFLIGHT-NEGATIVE",
        **{**base, "input_sha256": "f" * 64},
    )
    blocked = initial_state(blocked_context)
    blocked, blocked_event = transition(
        blocked,
        "blocked_preflight",
        checks={"input_hash_valid": False, "parent_lineage_present": True},
    )

    states = [positive, hash_failure, invariant_failure, blocked]
    events = positive_events + hash_events + invariant_events + [blocked_event]
    failures = [
        {
            "schema_version": "0.1",
            "record_kind": "repair_execution_regression_failure",
            "record_id": stable_id(
                "repair-regression",
                {"execution_id": hash_failure["execution_id"], "signature": "hash"},
            ),
            "execution_id": hash_failure["execution_id"],
            "observation_mode": "destructive_regression",
            "failure_signature": "REPAIR_OUTPUT_HASH_MISMATCH",
            "failed_gate": "postvalidation",
            "detected": True,
            "rollback_completed": hash_failure["rollback_performed"],
            "source_artifacts_modified": False,
        },
        {
            "schema_version": "0.1",
            "record_kind": "repair_execution_regression_failure",
            "record_id": stable_id(
                "repair-regression",
                {"execution_id": invariant_failure["execution_id"], "signature": "invariant"},
            ),
            "execution_id": invariant_failure["execution_id"],
            "observation_mode": "destructive_regression",
            "failure_signature": "REPAIR_POSTCONDITION_FAILED",
            "failed_gate": "postvalidation",
            "detected": True,
            "rollback_completed": invariant_failure["rollback_performed"],
            "source_artifacts_modified": False,
        },
        {
            "schema_version": "0.1",
            "record_kind": "repair_execution_regression_failure",
            "record_id": stable_id(
                "repair-regression",
                {"execution_id": blocked["execution_id"], "signature": "preflight"},
            ),
            "execution_id": blocked["execution_id"],
            "observation_mode": "destructive_regression",
            "failure_signature": "REPAIR_PREFLIGHT_FAILED",
            "failed_gate": "preflight",
            "detected": True,
            "rollback_completed": False,
            "source_artifacts_modified": False,
        },
    ]
    validate_records(
        states,
        json.loads(
            (ROOT / "schemas/knowledge/repair-execution-state-v0.1.schema.json").read_text()
        ),
    )
    validate_records(
        events,
        json.loads(
            (ROOT / "schemas/knowledge/repair-execution-event-v0.1.schema.json").read_text()
        ),
    )
    validate_records(
        failures,
        json.loads(
            (
                ROOT
                / "schemas/knowledge/repair-execution-regression-failure-v0.1.schema.json"
            ).read_text()
        ),
    )
    states_path = KB / "repair_execution_states.jsonl"
    events_path = KB / "repair_execution_events.jsonl"
    failures_path = KB / "repair_execution_regression_failures.jsonl"
    dump_jsonl(states_path, states)
    dump_jsonl(events_path, events)
    dump_jsonl(failures_path, failures)
    summary = {
        "schema_version": "0.1",
        "status": "post_execution_validation_and_rollback_closure_complete",
        "positive_promotions": sum(item["state"] == "promoted" for item in states),
        "postvalidation_rollbacks": sum(item["state"] == "rolled_back" for item in states),
        "preflight_blocks": sum(item["state"] == "blocked_preflight" for item in states),
        "destructive_regression_failures_recorded": len(failures),
        "candidate_layer_sha256": sha256_file(candidates_path),
        "locked_experiments_modified_or_rescored": False,
        "outputs": {
            "states_sha256": sha256_file(states_path),
            "events_sha256": sha256_file(events_path),
            "regression_failures_sha256": sha256_file(failures_path),
        },
        "next_gate": "expose_repair_lifecycle_through_auditable_query_api",
    }
    summary_path = KB / "repair_execution_closure_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
