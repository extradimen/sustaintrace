from __future__ import annotations

from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id


def prepare_workbench_repair_dispatch(
    *,
    plan: dict[str, Any],
    fact: dict[str, Any],
    source_path: Path | None,
    workspace_root: Path,
) -> dict[str, Any]:
    """Preflight a job-local repair without starting or promoting anything."""
    routes = plan.get("routes", [])
    expected_sha256 = fact.get("provenance", {}).get("source_sha256")
    resolved_source = source_path
    if resolved_source is None:
        source_artifact = fact.get("provenance", {}).get("source_artifact")
        if source_artifact:
            candidate = Path(source_artifact)
            resolved_source = candidate if candidate.is_absolute() else workspace_root / candidate
    source_valid = bool(
        resolved_source
        and resolved_source.is_file()
        and expected_sha256
        and sha256_file(resolved_source) == expected_sha256
    )
    checks = {
        "parent_fact_present": bool(fact.get("record_id")),
        "source_frozen_hash_valid": source_valid,
        "plan_is_read_only": plan.get("plan_state") == "planned_read_only",
        "execution_not_started": plan.get("execution_performed") is False,
        "promotion_not_started": plan.get("promotion_performed") is False,
        "routes_present": bool(routes),
        "all_routes_catalogued": all(route.get("strategy_id") for route in routes),
        "no_unresolved_blockers": not plan.get("unresolved_blocking_reasons"),
    }
    blocking_reasons = [name for name, passed in checks.items() if not passed]
    route_policies = {route.get("execution_policy") for route in routes}
    if "blocked" in route_policies:
        blocking_reasons.append("strategy_policy_blocks_execution")

    if blocking_reasons:
        decision = "blocked"
    elif all(
        route.get("execution_policy") == "automatic"
        and route.get("risk_level") == "low"
        and route.get("maturity") == "unseen_validated"
        for route in routes
    ):
        decision = "ready_for_automatic_execution"
    else:
        decision = "ready_for_supervised_execution"

    identity = {
        "repair_plan_id": plan["repair_plan_id"],
        "fact_record_id": fact["record_id"],
        "source_sha256": expected_sha256,
        "checks": checks,
        "decision": decision,
    }
    return {
        "schema_version": "1.0",
        "record_kind": "workbench_repair_dispatch",
        "dispatch_id": stable_id("workbench-repair-dispatch", identity),
        "repair_plan_id": plan["repair_plan_id"],
        "fact_record_id": fact["record_id"],
        "decision": decision,
        "checks": checks,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "execution_started": False,
        "execution_state": "planned",
        "promotion_performed": False,
        "cloud_transfer_performed": False,
        "locked_experiments_modified": False,
    }


def prepare_workbench_repair_dispatches(
    *,
    plans: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    source_path: Path | None,
    workspace_root: Path,
) -> list[dict[str, Any]]:
    facts_by_id = {fact["record_id"]: fact for fact in facts}
    records = []
    for plan in plans:
        fact = facts_by_id.get(plan["fact_record_id"])
        if fact is None:
            continue
        records.append(
            prepare_workbench_repair_dispatch(
                plan=plan,
                fact=fact,
                source_path=source_path,
                workspace_root=workspace_root,
            )
        )
    return records
