from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _index_one(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["fact_record_id"]: record for record in records}


def _index_many(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        indexed[record["fact_record_id"]].append(record)
    return dict(indexed)


def _is_promoted_tier_b(
    fact: dict[str, Any],
    qualification: dict[str, Any] | None,
    independent_adjudication: dict[str, Any] | None,
) -> bool:
    return bool(
        fact.get("trust_tier") == "B"
        and fact.get("knowledge_status") == "promoted_validated_fact"
        and fact.get("promotion", {}).get("eligible") is True
        and qualification
        and qualification.get("qualification_status") == "jointly_qualified_candidate"
        and independent_adjudication
        and independent_adjudication.get("promotion_decision", {}).get("eligible") is True
    )


def _matches(
    fact: dict[str, Any],
    *,
    task_id: str | None,
    document_id: str | None,
    company: str | None,
    predicate: str | None,
) -> bool:
    subject = fact.get("subject", {})
    if task_id and subject.get("task_id") != task_id:
        return False
    if document_id and document_id not in subject.get("document_ids", []):
        return False
    if predicate and fact.get("predicate", {}).get("canonical_key") != predicate:
        return False
    if company:
        target = company.casefold()
        companies = [
            str(item.get("company", "")).casefold() for item in subject.get("document_metadata", [])
        ]
        if not any(target in item for item in companies):
            return False
    return True


def query_facts(
    knowledge_base_directory: str | Path,
    *,
    task_id: str | None = None,
    document_id: str | None = None,
    company: str | None = None,
    predicate: str | None = None,
    include_candidates: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Query facts without allowing candidates to masquerade as trusted knowledge."""
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if offset < 0:
        raise ValueError("offset must be non-negative")

    root = Path(knowledge_base_directory)
    facts = _load_jsonl(root / "fact_records.jsonl")
    trusted_records = _load_jsonl(root / "trusted_fact_records.jsonl")
    trusted_overlays = {record["record_id"]: record for record in trusted_records}
    fact_ids = {record["record_id"] for record in facts}
    facts = [trusted_overlays.get(record["record_id"], record) for record in facts]
    facts.extend(record for record in trusted_records if record["record_id"] not in fact_ids)
    promotions = _index_one(_load_jsonl(root / "fact_promotion_audits.jsonl"))
    qualifications = _index_one(_load_jsonl(root / "joint_fact_qualifications.jsonl"))
    independent_adjudications = _index_one(
        _load_jsonl(root / "tier_b_independent_adjudications.jsonl")
    )
    native = _index_one(_load_jsonl(root / "native_pdf_corroborations.jsonl"))
    adjudication = _index_one(_load_jsonl(root / "tier_b_adjudication_queue.jsonl"))
    gaps = _index_many(_load_jsonl(root / "knowledge_gap_records.jsonl"))

    selected: list[dict[str, Any]] = []
    trusted_count = 0
    candidate_count = 0
    for fact in facts:
        fact_id = fact["record_id"]
        promotion = promotions.get(fact_id)
        qualification = qualifications.get(fact_id)
        independent_adjudication = independent_adjudications.get(fact_id)
        trusted = fact_id in trusted_overlays or _is_promoted_tier_b(
            fact, qualification, independent_adjudication
        )
        if trusted:
            trusted_count += 1
        else:
            candidate_count += 1
        if not trusted and not include_candidates:
            continue
        if not _matches(
            fact,
            task_id=task_id,
            document_id=document_id,
            company=company,
            predicate=predicate,
        ):
            continue
        selected.append(
            {
                "fact": fact,
                "effective_trust": "trusted_tier_b" if trusted else "candidate_not_trusted",
                "promotion_audit": promotion,
                "joint_qualification": qualification,
                "independent_adjudication": independent_adjudication,
                "native_pdf_corroboration": native.get(fact_id),
                "tier_b_adjudication": adjudication.get(fact_id),
                "unresolved_gaps": [] if trusted else gaps.get(fact_id, []),
            }
        )

    page = selected[offset : offset + limit]
    return {
        "schema_version": "0.1",
        "record_kind": "fact_query_response",
        "policy": {
            "default_scope": "promoted_tier_b_only",
            "include_candidates": include_candidates,
            "candidates_are_never_reported_as_trusted": True,
        },
        "filters": {
            "task_id": task_id,
            "document_id": document_id,
            "company": company,
            "predicate": predicate,
        },
        "inventory": {
            "facts": len(facts),
            "trusted_tier_b": trusted_count,
            "candidates_not_trusted": candidate_count,
        },
        "pagination": {
            "matched": len(selected),
            "returned": len(page),
            "offset": offset,
            "limit": limit,
        },
        "records": page,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _group_by(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        value = record.get(key)
        if isinstance(value, str):
            grouped[value].append(record)
    return dict(grouped)


def query_repair_lifecycle(
    knowledge_base_directory: str | Path,
    strategy_catalog_path: str | Path,
    *,
    execution_id: str | None = None,
    state: str | None = None,
    failure_signature: str | None = None,
    include_regression_observations: bool = False,
) -> dict[str, Any]:
    """Query failures, repair plans and executions without hiding negative outcomes."""
    allowed_states = {
        "planned",
        "preflight_passed",
        "blocked_preflight",
        "executed",
        "failed_execution",
        "postvalidation_passed",
        "postvalidation_failed",
        "promoted",
        "rolled_back",
    }
    if state is not None and state not in allowed_states:
        raise ValueError(f"unsupported repair execution state: {state}")

    root = Path(knowledge_base_directory)
    workspace = Path(strategy_catalog_path).resolve().parents[2]
    failures = _load_jsonl(root / "failure_records.jsonl")
    plans = _load_jsonl(root / "repair_controller_dry_run.jsonl")
    validations = _load_jsonl(root / "automatic_candidate_validations.jsonl")
    execution_states = _load_jsonl(root / "repair_execution_states.jsonl")
    events = _load_jsonl(root / "repair_execution_events.jsonl")
    regression_failures = _load_jsonl(root / "repair_execution_regression_failures.jsonl")
    dispatch_decisions = _load_jsonl(root / "repair_dispatch_decisions.jsonl")
    execution_sources = {
        record["execution_id"]: "data/knowledge_bases/v0.1/repair_execution_states.jsonl"
        for record in execution_states
    }
    operations_root = workspace / "data/operations/repair_cases"
    for state_path in sorted(operations_root.glob("*/execution_state.lock.json")):
        record = _load_json(state_path)
        execution_states.append(record)
        execution_sources[record["execution_id"]] = state_path.relative_to(workspace).as_posix()
        events.extend(_load_jsonl(state_path.with_name("execution_events.jsonl")))
        dispatch_path = state_path.with_name("dispatch_decision.lock.json")
        if dispatch_path.exists():
            dispatch_decisions.append(_load_json(dispatch_path))
    facts = _load_jsonl(root / "fact_records.jsonl")
    catalog = _load_json(Path(strategy_catalog_path))

    failure_by_id = {record["record_id"]: record for record in failures}
    fact_by_id = {record["record_id"]: record for record in facts}
    plan_by_failure = {record["failure_record_id"]: record for record in plans}
    validation_by_plan = {record["plan_id"]: record for record in validations}
    strategies = {record["strategy_id"]: record for record in catalog.get("strategies", [])}
    events_by_execution = _group_by(events, "execution_id")
    regression_by_execution = _group_by(regression_failures, "execution_id")

    failure_cases = []
    for failure in failures:
        if failure_signature and failure.get("failure_signature") != failure_signature:
            continue
        plan = plan_by_failure.get(failure["record_id"])
        failure_cases.append(
            {
                "failure": failure,
                "repair_plan": plan,
                "validation": validation_by_plan.get(plan["plan_id"]) if plan else None,
                "strategy": strategies.get(plan["strategy_id"]) if plan else None,
            }
        )

    executions = []
    for execution in execution_states:
        if execution_id and execution.get("execution_id") != execution_id:
            continue
        if state and execution.get("state") != state:
            continue
        observations = regression_by_execution.get(execution["execution_id"], [])
        if failure_signature and not any(
            item.get("failure_signature") == failure_signature for item in observations
        ):
            continue
        ordered_events = sorted(
            events_by_execution.get(execution["execution_id"], []),
            key=lambda item: item["sequence"],
        )
        parent_id = execution["parent_record_id"]
        promoted_safely = bool(
            execution["state"] == "promoted"
            and execution.get("promotion_performed") is True
            and any(item["to_state"] == "postvalidation_passed" for item in ordered_events)
        )
        executions.append(
            {
                "execution": execution,
                "source_artifact": execution_sources[execution["execution_id"]],
                "effective_outcome": (
                    "successful_validated_repair" if promoted_safely else "not_a_successful_repair"
                ),
                "events": ordered_events,
                "parent_lineage": {
                    "kind": (
                        "failure_observation"
                        if parent_id in failure_by_id
                        else "fact_record"
                        if parent_id in fact_by_id
                        else "unresolved_parent"
                    ),
                    "record": failure_by_id.get(parent_id) or fact_by_id.get(parent_id),
                },
                "strategy": strategies.get(execution["strategy_id"]),
                "regression_observations": (
                    observations if include_regression_observations else []
                ),
            }
        )

    state_counts: dict[str, int] = defaultdict(int)
    for record in execution_states:
        state_counts[record["state"]] += 1
    return {
        "schema_version": "0.1",
        "record_kind": "repair_lifecycle_query_response",
        "policy": {
            "negative_outcomes_are_preserved": True,
            "blocked_or_rolled_back_are_never_successful": True,
            "promotion_requires_postvalidation_event": True,
            "regression_observations_included": include_regression_observations,
        },
        "filters": {
            "execution_id": execution_id,
            "state": state,
            "failure_signature": failure_signature,
        },
        "inventory": {
            "failure_observations": len(failures),
            "failure_signatures": len({item["failure_signature"] for item in failures}),
            "repair_strategies": len(strategies),
            "repair_plans": len(plans),
            "candidate_validations": len(validations),
            "repair_executions": len(execution_states),
            "execution_states": dict(sorted(state_counts.items())),
            "regression_observations": len(regression_failures),
            "dispatch_decisions": len(dispatch_decisions),
            "dispatch_ready": sum(
                item.get("decision") == "ready_for_execution" for item in dispatch_decisions
            ),
            "dispatch_blocked": sum(
                item.get("decision") == "blocked" for item in dispatch_decisions
            ),
        },
        "matched": {
            "failure_cases": len(failure_cases),
            "executions": len(executions),
        },
        "failure_cases": failure_cases,
        "executions": executions,
        "dispatch_decisions": dispatch_decisions,
    }


def query_control_plane(
    knowledge_base_directory: str | Path,
    strategy_catalog_path: str | Path,
    *,
    include_candidates: bool = False,
    include_regression_observations: bool = False,
) -> dict[str, Any]:
    """Expose the fact and failure-repair stores through one policy-preserving response."""
    return {
        "schema_version": "0.1",
        "record_kind": "esg_control_plane_query_response",
        "policy": {
            "read_only": True,
            "locked_experiments_modified_or_rescored": False,
            "candidate_facts_require_explicit_opt_in": True,
            "repair_success_requires_postvalidation": True,
        },
        "facts": query_facts(
            knowledge_base_directory,
            include_candidates=include_candidates,
            limit=1000,
        ),
        "repairs": query_repair_lifecycle(
            knowledge_base_directory,
            strategy_catalog_path,
            include_regression_observations=include_regression_observations,
        ),
    }
