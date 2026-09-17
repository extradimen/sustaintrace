from __future__ import annotations

from collections import defaultdict
from typing import Any

from .knowledge_base import stable_id

BLOCKER_ROUTES: dict[str, str] = {
    "PREDICATE_AMBIGUOUS": "SEMANTIC_PROJECTION_MISMATCH",
    "PERIOD_BINDING_AMBIGUOUS": "PARSER_TABLE_STRUCTURE",
    "PERIOD_BINDING_MISSING": "PARSER_TABLE_STRUCTURE",
    "PERIOD_BINDING_INCOMPLETE": "PARSER_TABLE_STRUCTURE",
    "UNIT_BINDING_AMBIGUOUS": "PARSER_TABLE_STRUCTURE",
    "UNIT_BINDING_MISSING": "PARSER_TABLE_STRUCTURE",
    "UNIT_BINDING_INCOMPLETE": "PARSER_TABLE_STRUCTURE",
    "PAGE_LOCATOR_MISSING": "PARSER_TABLE_STRUCTURE",
    "SPATIAL_LOCATOR_MISSING": "PARSER_TABLE_STRUCTURE",
    "FIELD_OR_CELL_BINDING_INCOMPLETE": "PARSER_TABLE_STRUCTURE",
    "VERBATIM_LITERAL_NOT_GROUNDED": "EVIDENCE_GROUNDING_MISMATCH",
    "RAW_EVIDENCE_INCOMPLETE": "EVIDENCE_GROUNDING_MISMATCH",
    "SCOPE_BINDING_INCOMPLETE": "EVIDENCE_SELECTION_GAP",
    "INDEPENDENT_CORROBORATION_INCOMPLETE": "EVIDENCE_SELECTION_GAP",
    "SOURCE_METADATA_MISSING": "PREFLIGHT_CONTRACT_GATE",
    "SOURCE_PATH_OR_HASH_MISSING": "PREFLIGHT_CONTRACT_GATE",
}


def _strategy_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        signature: strategy
        for strategy in catalog.get("strategies", [])
        for signature in strategy.get("target_signatures", [])
    }


def _normalize_reason(reason: str) -> str:
    return reason.removeprefix("OPEN_GAP:")


def plan_workbench_repairs(
    *,
    failures: list[dict[str, Any]],
    promotion_gates: list[dict[str, Any]],
    strategy_catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create explainable, non-executing plans for job-local blocked facts."""
    strategy_by_signature = _strategy_index(strategy_catalog)
    failures_by_fact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for failure in failures:
        fact_id = failure.get("parent_fact_record_id")
        if fact_id:
            failures_by_fact[fact_id].append(failure)

    records: list[dict[str, Any]] = []
    for gate in promotion_gates:
        if gate.get("decision") != "blocked":
            continue
        fact_id = gate["fact_record_id"]
        related_failures = failures_by_fact.get(fact_id, [])
        reasons = {
            _normalize_reason(str(reason))
            for reason in gate.get("blocking_reasons", [])
        }
        for failure in related_failures:
            reasons.update(str(reason) for reason in failure.get("blocking_reasons", []))

        routes = []
        unresolved = []
        for reason in sorted(reasons):
            catalog_signature = BLOCKER_ROUTES.get(reason)
            strategy = strategy_by_signature.get(catalog_signature) if catalog_signature else None
            if strategy is None:
                unresolved.append(reason)
                continue
            routes.append(
                {
                    "blocking_reason": reason,
                    "catalog_signature": catalog_signature,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_name": strategy["name"],
                    "risk_level": strategy["risk_level"],
                    "execution_policy": strategy["execution_policy"],
                    "maturity": strategy["maturity"],
                    "actions": strategy["actions"],
                    "validation_gates": strategy["validation_gates"],
                }
            )

        policies = {route["execution_policy"] for route in routes}
        if unresolved or "blocked" in policies:
            decision = "blocked_fail_closed"
        elif "supervised" in policies:
            decision = "supervised_candidate"
        elif routes:
            decision = "automatic_candidate_not_executed"
        else:
            decision = "no_strategy"
        identity = {
            "fact_record_id": fact_id,
            "gate_id": gate.get("dry_run_id"),
            "routes": [(item["blocking_reason"], item["strategy_id"]) for item in routes],
            "unresolved": unresolved,
        }
        records.append(
            {
                "schema_version": "1.0",
                "record_kind": "workbench_repair_plan",
                "repair_plan_id": stable_id("workbench-repair-plan", identity),
                "fact_record_id": fact_id,
                "source_failure_record_ids": sorted(
                    item["record_id"] for item in related_failures
                ),
                "promotion_gate_id": gate.get("dry_run_id"),
                "plan_state": "planned_read_only",
                "decision": decision,
                "routes": routes,
                "unresolved_blocking_reasons": unresolved,
                "postvalidation_requirements": sorted(
                    {
                        validation
                        for route in routes
                        for validation in route["validation_gates"]
                    }
                ),
                "rollback": "discard derived plan and preserve the parent fact and failures",
                "execution_performed": False,
                "promotion_performed": False,
                "cloud_transfer_performed": False,
                "locked_experiments_modified": False,
            }
        )
    return records
