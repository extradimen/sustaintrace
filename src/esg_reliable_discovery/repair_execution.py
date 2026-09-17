from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from esg_reliable_discovery.knowledge_base import stable_id


class InvalidRepairTransition(ValueError):
    """Raised when a repair lifecycle attempts to bypass a required gate."""


ALLOWED_TRANSITIONS = {
    "planned": {"preflight_passed", "blocked_preflight"},
    "preflight_passed": {"executed", "failed_execution"},
    "executed": {"postvalidation_passed", "postvalidation_failed"},
    "postvalidation_passed": {"promoted"},
    "postvalidation_failed": {"rolled_back"},
    "failed_execution": {"rolled_back"},
    "blocked_preflight": set(),
    "promoted": set(),
    "rolled_back": set(),
}


@dataclass(frozen=True)
class RepairExecutionContext:
    plan_id: str
    parent_record_id: str
    strategy_id: str
    validator_id: str
    input_sha256: str
    expected_output_sha256: str
    rollback_action: str
    invariants: tuple[str, ...]


def initial_state(context: RepairExecutionContext) -> dict[str, Any]:
    identity = {
        "plan_id": context.plan_id,
        "parent_record_id": context.parent_record_id,
        "strategy_id": context.strategy_id,
        "input_sha256": context.input_sha256,
    }
    return {
        "schema_version": "0.1",
        "record_kind": "repair_execution_state",
        "execution_id": stable_id("repair-execution", identity),
        "plan_id": context.plan_id,
        "parent_record_id": context.parent_record_id,
        "strategy_id": context.strategy_id,
        "validator_id": context.validator_id,
        "state": "planned",
        "input_sha256": context.input_sha256,
        "expected_output_sha256": context.expected_output_sha256,
        "actual_output_sha256": None,
        "invariants": list(context.invariants),
        "invariant_results": {},
        "rollback_action": context.rollback_action,
        "promotion_performed": False,
        "rollback_performed": False,
        "event_sequence": 0,
    }


def transition(
    state: dict[str, Any],
    next_state: str,
    *,
    checks: dict[str, bool],
    actual_output_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = state["state"]
    if next_state not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidRepairTransition(f"invalid repair transition: {current} -> {next_state}")
    if next_state in {
        "preflight_passed",
        "executed",
        "postvalidation_passed",
        "promoted",
        "rolled_back",
    } and (not checks or not all(checks.values())):
        raise InvalidRepairTransition(f"passing transition has failed checks: {next_state}")
    if next_state == "promoted" and current != "postvalidation_passed":
        raise InvalidRepairTransition("promotion requires passed postvalidation")
    if next_state == "rolled_back" and current not in {
        "postvalidation_failed",
        "failed_execution",
    }:
        raise InvalidRepairTransition("rollback requires an execution or postvalidation failure")

    updated = dict(state)
    updated["state"] = next_state
    updated["event_sequence"] = state["event_sequence"] + 1
    if actual_output_sha256 is not None:
        updated["actual_output_sha256"] = actual_output_sha256
    if current == "executed":
        updated["invariant_results"] = dict(checks)
    if next_state == "promoted":
        updated["promotion_performed"] = True
    if next_state == "rolled_back":
        updated["rollback_performed"] = True

    event_identity = {
        "execution_id": state["execution_id"],
        "sequence": updated["event_sequence"],
        "from": current,
        "to": next_state,
        "checks": checks,
        "actual_output_sha256": actual_output_sha256,
    }
    event = {
        "schema_version": "0.1",
        "record_kind": "repair_execution_event",
        "event_id": stable_id("repair-event", event_identity),
        "execution_id": state["execution_id"],
        "sequence": updated["event_sequence"],
        "from_state": current,
        "to_state": next_state,
        "checks": dict(checks),
        "input_sha256": state["input_sha256"],
        "expected_output_sha256": state["expected_output_sha256"],
        "actual_output_sha256": updated["actual_output_sha256"],
        "validator_id": state["validator_id"],
        "rollback_action": state["rollback_action"],
    }
    return updated, event


def postvalidate(
    state: dict[str, Any],
    *,
    actual_output_sha256: str,
    invariant_results: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_invariants = set(state["invariants"])
    if set(invariant_results) != expected_invariants:
        raise InvalidRepairTransition(
            "postvalidation must report every frozen invariant exactly once"
        )
    checks = {
        "output_sha256_matches": actual_output_sha256 == state["expected_output_sha256"],
        **invariant_results,
    }
    next_state = "postvalidation_passed" if all(checks.values()) else "postvalidation_failed"
    return transition(
        state,
        next_state,
        checks=checks,
        actual_output_sha256=actual_output_sha256,
    )
