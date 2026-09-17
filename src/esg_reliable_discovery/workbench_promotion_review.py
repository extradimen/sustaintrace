from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .knowledge_base import stable_id

ALLOWED_DECISIONS = {
    "approve_for_promotion_staging": "approved_for_promotion_staging",
    "reject": "rejected",
    "request_more_evidence": "evidence_required",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_promotion_review_queue(
    *,
    repaired_facts: list[dict[str, Any]],
    repair_executions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create job-local review records without changing fact or trusted layers."""
    facts = {fact["record_id"]: fact for fact in repaired_facts}
    records = []
    for execution in repair_executions:
        fact_id = execution.get("derived_fact_record_id")
        fact = facts.get(fact_id)
        if execution.get("state") != "postvalidation_passed" or fact is None:
            continue
        checks = {
            "postvalidation_passed": True,
            "all_execution_checks_passed": bool(execution.get("checks"))
            and all(execution["checks"].values()),
            "input_is_tier_c_candidate": fact.get("trust_tier") == "C",
            "promotion_not_previously_performed": execution.get("promotion_performed") is False,
            "trusted_layer_unchanged": execution.get("trusted_layer_modified") is False,
            "cloud_transfer_not_performed": execution.get("cloud_transfer_performed") is False,
        }
        if not all(checks.values()):
            continue
        identity = {
            "fact_record_id": fact_id,
            "execution_id": execution["execution_id"],
            "requested_trust_tier": "B",
        }
        records.append(
            {
                "schema_version": "1.0",
                "record_kind": "workbench_promotion_review",
                "review_id": stable_id("workbench-promotion-review", identity),
                "fact_record_id": fact_id,
                "parent_fact_record_id": execution["parent_fact_record_id"],
                "repair_execution_id": execution["execution_id"],
                "requested_trust_tier": "B",
                "state": "pending_review",
                "version": 1,
                "preconditions": checks,
                "allowed_decisions": sorted(ALLOWED_DECISIONS),
                "decision_history": [],
                "promotion_performed": False,
                "trusted_layer_modified": False,
                "rollback_action": "discard review record and preserve Tier C candidate",
            }
        )
    return records


def decide_promotion_review(
    record: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    rationale: str,
    expected_version: int,
) -> dict[str, Any]:
    """Apply one auditable review decision; approval only stages a later promotion."""
    if record.get("state") != "pending_review":
        raise ValueError("promotion review is no longer pending")
    if record.get("version") != expected_version:
        raise ValueError("promotion review version conflict")
    if decision not in ALLOWED_DECISIONS:
        raise ValueError("unsupported promotion review decision")
    reviewer = " ".join(reviewer.split())
    rationale = " ".join(rationale.split())
    if not reviewer or not rationale:
        raise ValueError("reviewer and rationale are required")

    updated = deepcopy(record)
    event = {
        "event_id": stable_id(
            "workbench-promotion-review-event",
            {
                "review_id": record["review_id"],
                "version": expected_version + 1,
                "decision": decision,
                "reviewer": reviewer,
                "rationale": rationale,
            },
        ),
        "at": _now(),
        "from_state": "pending_review",
        "to_state": ALLOWED_DECISIONS[decision],
        "decision": decision,
        "reviewer": reviewer,
        "rationale": rationale,
    }
    updated["state"] = event["to_state"]
    updated["version"] = expected_version + 1
    updated["updated_at"] = event["at"]
    updated["decision_history"] = [*record.get("decision_history", []), event]
    updated["promotion_performed"] = False
    updated["trusted_layer_modified"] = False
    return updated
