from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id


def plan_evidence_repair_with_contract(
    failure: dict[str, Any],
    contract_catalog: dict[str, Any],
    *,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Route an evidence failure and bind its fail-closed policy contract."""
    from esg_reliable_discovery.evidence_repair_triage import (
        bind_evidence_contract,
        plan_evidence_repair,
    )

    plan = plan_evidence_repair(failure, mode=mode)
    return plan, bind_evidence_contract(plan, contract_catalog)


def index_strategies(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for strategy in catalog.get("strategies", []):
        for signature in strategy.get("target_signatures", []):
            if signature in index:
                raise ValueError(f"duplicate repair strategy for signature: {signature}")
            index[signature] = strategy
    return index


def plan_repair(
    failure: dict[str, Any],
    strategy_index: dict[str, dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"locked_evaluation", "operational"}:
        raise ValueError(f"unsupported controller mode: {mode}")
    strategy = strategy_index.get(failure["failure_signature"])
    identity = {
        "failure_record_id": failure["record_id"],
        "mode": mode,
        "strategy_id": strategy.get("strategy_id") if strategy else None,
    }
    if strategy is None:
        decision = "no_strategy"
    elif mode == "locked_evaluation":
        decision = "archive_only"
    else:
        policy = strategy["execution_policy"]
        if policy == "automatic" and strategy["maturity"] == "unseen_validated":
            decision = "automatic_candidate"
        elif policy == "blocked":
            decision = "blocked"
        else:
            decision = "supervised"
    return {
        "schema_version": "0.1",
        "plan_id": stable_id("plan", identity),
        "failure_record_id": failure["record_id"],
        "mode": mode,
        "decision": decision,
        "strategy_id": strategy.get("strategy_id") if strategy else None,
        "actions": strategy.get("actions", []) if strategy else [],
        "validation_gates": strategy.get("validation_gates", []) if strategy else [],
        "rollback": (
            strategy.get("rollback", "preserve failure and stop")
            if strategy
            else "preserve failure and stop"
        ),
        "execution_performed": False,
    }


def validate_automatic_candidate(
    plan: dict[str, Any],
    failure: dict[str, Any],
    strategy: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    diagnostic_text = json.dumps(failure.get("diagnostics", []), ensure_ascii=False).casefold()
    source_path = root / failure["provenance"]["source_artifact"]
    checks = {
        "operational_mode": plan["mode"] == "operational",
        "automatic_candidate_decision": plan["decision"] == "automatic_candidate",
        "execution_not_started": plan["execution_performed"] is False,
        "unseen_validated_strategy": strategy["maturity"] == "unseen_validated",
        "low_risk_strategy": strategy["risk_level"] == "low",
        "failure_source_hash_valid": (
            source_path.is_file()
            and sha256_file(source_path) == failure["provenance"]["source_sha256"]
        ),
        "evidence_artifacts_present": all(
            (root / path).exists() for path in strategy["evidence_artifacts"]
        ),
        "exact_alias_diagnosis_present": (
            failure["failure_signature"] == "HANDLE_CANONICALIZATION_MISMATCH"
            and "exact alias" in diagnostic_text
            and "no invalid handles" in diagnostic_text
        ),
    }
    ready = all(checks.values())
    return {
        "schema_version": "0.1",
        "plan_id": plan["plan_id"],
        "failure_record_id": failure["record_id"],
        "strategy_id": strategy["strategy_id"],
        "validation_status": "ready_not_executed" if ready else "not_ready",
        "checks": checks,
        "execution_performed": False,
        "rollback_ledger": {
            "ledger_id": stable_id(
                "rollback", {"plan_id": plan["plan_id"], "failure": failure["record_id"]}
            ),
            "parent_failure_record_id": failure["record_id"],
            "parent_artifact": failure["provenance"]["source_artifact"],
            "parent_sha256": failure["provenance"]["source_sha256"],
            "status": "prepared_not_executed",
            "rollback_action": strategy["rollback"],
        },
    }


def plan_boundary_repair(
    negative_case: dict[str, Any],
    ontology: dict[str, Any],
    validator_catalog: dict[str, Any],
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan a semantic-boundary repair without relaxing the fail-closed policy."""
    boundary_class = negative_case["boundary_class"]
    class_policy = ontology["classes"].get(boundary_class)
    if class_policy is None:
        raise ValueError(f"unknown boundary class: {boundary_class}")
    validators = {item["boundary_class"]: item for item in validator_catalog.get("validators", [])}
    validator = validators.get(boundary_class)
    enabled = bool(validator and validator.get("status") == "enabled")
    validation_ready = bool(
        validation
        and validation.get("case_id") == negative_case["case_id"]
        and validation.get("validation_status") == "ready_for_supervised_execution"
        and all(validation.get("checks", {}).values())
    )
    if not enabled:
        decision = "blocked_missing_class_validator"
    elif not validation_ready:
        decision = "blocked_validation_missing_or_failed"
    else:
        decision = "supervised_candidate"
    identity = {
        "case_id": negative_case["case_id"],
        "validator_id": validator.get("validator_id") if validator else None,
        "validation_id": validation.get("validation_id") if validation_ready else None,
        "decision": decision,
    }
    return {
        "schema_version": "0.1",
        "plan_id": stable_id("boundary-plan", identity),
        "case_id": negative_case["case_id"],
        "fact_record_id": negative_case["fact_record_id"],
        "boundary_class": boundary_class,
        "decision": decision,
        "validator_id": validator.get("validator_id") if validator else None,
        "validation_id": validation.get("validation_id") if validation_ready else None,
        "allowed_evidence_patterns": class_policy["allowed_evidence_patterns"],
        "rejected_shortcuts": class_policy["rejected_shortcuts"],
        "execution_performed": False,
        "promotion_performed": False,
        "rollback": "preserve unresolved candidate and remove derived plan",
    }


def validate_assurance_boundary_case(
    negative_case: dict[str, Any],
    fact: dict[str, Any],
    native_binding: dict[str, Any],
    period_resolution: dict[str, Any] | None,
    root: Path,
    resolved_boundary: str,
) -> dict[str, Any]:
    """Validate non-temporal assurance metadata against signed source context."""
    native_text = "\n".join(
        candidate.get("context", "") for candidate in native_binding.get("candidates", [])
    ).casefold()
    evidence_text = "\n".join(
        evidence.get("quote", "") for evidence in fact.get("evidence", [])
    ).casefold()
    combined = f"{native_text}\n{evidence_text}"
    value_literal = str(fact.get("value", "")).casefold()
    assurance_markers = ("assurance", "isae 3000")
    subject_markers = (
        "sustainability statement",
        "sustainability report",
        "sustainability disclosures",
        "double materiality assessment",
        "transition plan disclosures",
    )
    level_markers = ("limited assurance", "reasonable assurance")
    exclusion_markers = (
        "only covers",
        "not part",
        "outside",
        "not our responsibility",
        "do not express",
        "not covered",
        "not subject",
        "did not perform assurance",
    )
    document_hashes_valid = bool(fact["subject"].get("document_metadata")) and all(
        (root / metadata["local_path"]).is_file()
        and sha256_file(root / metadata["local_path"]) == metadata["sha256"]
        for metadata in fact["subject"].get("document_metadata", [])
    )
    checks = {
        "task_is_assurance": negative_case["task_id"].endswith("-ASSURE-001"),
        "source_document_hash_valid": document_hashes_valid,
        "literal_in_native_context": bool(value_literal) and value_literal in native_text,
        "assurance_context_present": any(marker in combined for marker in assurance_markers),
        "engagement_subject_present": any(marker in combined for marker in subject_markers),
        "assurance_level_present": any(marker in combined for marker in level_markers),
        "inclusion_or_exclusion_preserved": any(marker in combined for marker in exclusion_markers),
        "period_classified_non_temporal": bool(
            period_resolution
            and period_resolution.get("resolution_type") == "not_applicable_non_temporal_field"
        ),
        "native_binding_unique": native_binding.get("status") == "unique_context_binding",
    }
    ready = all(checks.values())
    identity = {
        "case_id": negative_case["case_id"],
        "fact_record_id": fact["record_id"],
        "resolved_boundary": resolved_boundary,
    }
    return {
        "schema_version": "0.1",
        "record_kind": "assurance_boundary_validation",
        "validation_id": stable_id("assurance-validation", identity),
        "case_id": negative_case["case_id"],
        "fact_record_id": fact["record_id"],
        "task_id": negative_case["task_id"],
        "predicate": negative_case["predicate"],
        "value": fact.get("value"),
        "resolved_boundary": resolved_boundary,
        "checks": checks,
        "validation_status": ("ready_for_supervised_execution" if ready else "not_ready"),
        "execution_performed": False,
        "promotion_performed": False,
        "rollback": "delete_validation_and_preserve_unresolved_candidate",
    }


def validate_metric_component_case(
    negative_case: dict[str, Any],
    fact: dict[str, Any],
    native_binding: dict[str, Any],
    table_graph: dict[str, Any],
    graph_path: Path,
    root: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Validate a scalar's row, column, component role, and applicable footnote."""
    native_text = "\n".join(
        item.get("context", "") for item in native_binding.get("candidates", [])
    ).casefold()
    evidence_text = "\n".join(item.get("quote", "") for item in fact.get("evidence", [])).casefold()
    graph = next(
        (item for item in table_graph.get("graphs", []) if item["graph_id"] == spec["graph_id"]),
        None,
    )
    document_hash_valid = bool(fact["subject"].get("document_metadata")) and all(
        (root / item["local_path"]).is_file()
        and sha256_file(root / item["local_path"]) == item["sha256"]
        for item in fact["subject"].get("document_metadata", [])
    )
    row_values = [str(item).casefold() for item in spec["row_values"]]
    positions = [native_text.find(item) for item in row_values]
    ordered_values = all(position >= 0 for position in positions) and positions == sorted(positions)
    selected_cells = graph.get("selected_cells", []) if graph else []
    exact_selected_cell = bool(
        graph
        and any(
            cell[0] == spec["row"] and cell[1] == spec["header"] and cell[2] == fact["value"]
            for cell in selected_cells
        )
    )
    sequence_cell = bool(
        graph
        and ordered_values
        and spec["value_index"] < len(row_values)
        and spec["value_index"] < len(graph["header_axis"])
        and graph["header_axis"][spec["value_index"]] == spec["header"]
        and row_values[spec["value_index"]] == spec["value_literal"].casefold()
    )
    checks = {
        "source_document_hash_valid": document_hash_valid,
        "table_graph_hash_valid": (
            graph_path.is_file() and sha256_file(graph_path) == spec["graph_sha256"]
        ),
        "table_graph_frozen": table_graph.get("status") == "frozen_before_candidate_inference",
        "graph_and_page_match": bool(
            graph
            and native_binding.get("pdf_page") in graph.get("pdf_pages", [graph.get("pdf_page")])
        ),
        "unique_native_binding": native_binding.get("status") == "unique_context_binding",
        "literal_in_native_context": spec["value_literal"].casefold() in native_text,
        "row_label_in_native_context": spec["row_alias"].casefold() in native_text,
        "row_axis_bound": bool(graph and spec["row"] in graph["row_axis"]),
        "column_header_bound": bool(graph and spec["header"] in graph["header_axis"]),
        "row_values_ordered": ordered_values,
        "cell_spatial_relation_bound": exact_selected_cell or sequence_cell,
        "component_role_bound": spec["component_role"] in {"component", "total"},
        "method_role_bound": (
            spec["method_role"] == "not_applicable" or spec["method_role"] in spec["header"]
        ),
        "applicable_footnote_preserved": (
            not spec.get("footnote")
            or f"{spec['value_literal']}{spec['footnote']}".casefold() in evidence_text
        ),
    }
    ready = all(checks.values())
    identity = {
        "case_id": negative_case["case_id"],
        "graph_id": spec["graph_id"],
        "row": spec["row"],
        "header": spec["header"],
    }
    return {
        "schema_version": "0.1",
        "record_kind": "metric_component_boundary_validation",
        "validation_id": stable_id("metric-validation", identity),
        "case_id": negative_case["case_id"],
        "fact_record_id": fact["record_id"],
        "task_id": negative_case["task_id"],
        "predicate": negative_case["predicate"],
        "value": fact["value"],
        "table_coordinate": {
            "graph_id": spec["graph_id"],
            "page": native_binding["pdf_page"],
            "row": spec["row"],
            "column": spec["header"],
            "component_role": spec["component_role"],
            "method_role": spec["method_role"],
            "footnote": spec.get("footnote"),
        },
        "checks": checks,
        "validation_status": ("ready_for_supervised_execution" if ready else "not_ready"),
        "execution_performed": False,
        "promotion_performed": False,
        "rollback": "delete_validation_and_preserve_unresolved_candidate",
    }


def validate_taxonomy_boundary_case(
    negative_case: dict[str, Any],
    fact: dict[str, Any],
    native_binding: dict[str, Any],
    root: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Validate EU Taxonomy role semantics while preserving audit-status blocks."""
    native_text = "\n".join(
        item.get("context", "") for item in native_binding.get("candidates", [])
    ).casefold()
    evidence_text = "\n".join(item.get("quote", "") for item in fact.get("evidence", [])).casefold()
    combined = f"{native_text}\n{evidence_text}"
    metadata = fact["subject"].get("document_metadata", [])
    source_hash_valid = bool(metadata) and all(
        (root / item["local_path"]).is_file()
        and sha256_file(root / item["local_path"]) == item["sha256"]
        for item in metadata
    )
    required_phrases_present = all(
        phrase.casefold() in combined for phrase in spec["required_phrases"]
    )
    forbidden_role_absent = all(
        phrase.casefold() not in spec["resolved_role"].casefold()
        for phrase in spec.get("forbidden_roles", [])
    )
    checks = {
        "source_document_hash_valid": source_hash_valid,
        "unique_native_binding": native_binding.get("status") == "unique_context_binding",
        "literal_in_native_context": spec["value_literal"].casefold() in native_text,
        "taxonomy_context_present": "taxonomy" in combined,
        "required_role_phrases_present": required_phrases_present,
        "resolved_role_specific": bool(spec["resolved_role"]),
        "denominator_eligibility_alignment_separated": forbidden_role_absent,
        "amount_or_percentage_bound": spec["value_kind"] in {"amount", "percentage"},
        "unit_bound": bool(spec["unit"]),
        "period_bound": bool(spec["period"]),
        "evidence_mode_explicit": spec["evidence_mode"]
        in {"native_table_row", "native_narrative_relation", "frozen_graph_and_native"},
        "audit_status_explicit": spec["audit_status"]
        in {"pending_independent_scope_review", "explicitly_unaudited"},
    }
    structurally_ready = all(checks.values())
    if structurally_ready and spec["audit_status"] == "explicitly_unaudited":
        status = "blocked_explicitly_unaudited"
    elif structurally_ready:
        status = "ready_for_supervised_execution"
    else:
        status = "not_ready"
    identity = {
        "case_id": negative_case["case_id"],
        "resolved_role": spec["resolved_role"],
        "value_kind": spec["value_kind"],
    }
    return {
        "schema_version": "0.1",
        "record_kind": "taxonomy_boundary_validation",
        "validation_id": stable_id("taxonomy-validation", identity),
        "case_id": negative_case["case_id"],
        "fact_record_id": fact["record_id"],
        "task_id": negative_case["task_id"],
        "predicate": negative_case["predicate"],
        "value": fact["value"],
        "resolved_classification": {
            "role": spec["resolved_role"],
            "value_kind": spec["value_kind"],
            "unit": spec["unit"],
            "period": spec["period"],
            "evidence_mode": spec["evidence_mode"],
            "audit_status": spec["audit_status"],
        },
        "checks": checks,
        "validation_status": status,
        "execution_performed": False,
        "promotion_performed": False,
        "rollback": "delete_validation_and_preserve_unresolved_candidate",
    }


def validate_organizational_population_case(
    negative_case: dict[str, Any],
    fact: dict[str, Any],
    native_binding: dict[str, Any],
    root: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Bind a workforce scalar to its consolidation and HR-system population."""
    native_text = "\n".join(
        item.get("context", "") for item in native_binding.get("candidates", [])
    ).casefold()
    evidence_text = "\n".join(item.get("quote", "") for item in fact.get("evidence", [])).casefold()
    supporting_text = str(spec.get("supporting_context", "")).casefold()
    combined = f"{native_text}\n{supporting_text}\n{evidence_text}"
    metadata = fact["subject"].get("document_metadata", [])
    source_hash_valid = bool(metadata) and all(
        (root / item["local_path"]).is_file()
        and sha256_file(root / item["local_path"]) == item["sha256"]
        for item in metadata
    )

    def literal_present(value: int) -> bool:
        variants = {str(value), f"{value:,}", f"{value:,}".replace(",", " ")}
        return any(item.casefold() in combined for item in variants)

    global_headcount = spec["global_headcount"]
    covered_headcount = spec["covered_headcount"]
    excluded_headcount = spec["excluded_headcount"]
    permanent = spec["permanent_employees"]
    temporary = spec["temporary_employees"]
    expected_value = {
        "global_headcount": global_headcount,
        "difference_headcount": excluded_headcount,
    }.get(negative_case["predicate"])
    checks = {
        "source_document_hash_valid": source_hash_valid,
        "unique_native_binding": native_binding.get("status") == "unique_context_binding",
        "task_is_workforce_population": negative_case["task_id"].endswith("-WORKFORCE-001"),
        "year_end_period_bound": "year-end 2025" in combined,
        "global_employee_population_present": literal_present(global_headcount)
        and "workforce comprised" in combined,
        "covered_employee_population_present": literal_present(covered_headcount)
        and "number of employees" in combined,
        "excluded_population_present": literal_present(excluded_headcount)
        and "excludes" in combined,
        "new_acquisition_exclusion_explicit": "newly acquired entities" in combined,
        "hr_system_coverage_explicit": "collected through sf" in combined
        and "had not yet implemented sf" in combined,
        "employee_type_components_present": literal_present(permanent)
        and literal_present(temporary)
        and "permanent employees" in combined
        and "temporary employees" in combined,
        "contract_components_reconcile": permanent + temporary == covered_headcount,
        "excluded_population_reconciles": covered_headcount + excluded_headcount
        == global_headcount,
        "employees_separated_from_non_employees": "non-employees" in combined,
        "predicate_value_matches_population_role": expected_value is not None
        and fact.get("value") == expected_value,
        "scope_role_explicit": spec["scope_role"]
        in {"global_group_employee_population", "hr_system_covered_employee_population_gap"},
        "audit_status_explicit": spec["audit_status"]
        in {"pending_independent_scope_review", "explicitly_unaudited"},
    }
    structurally_ready = all(checks.values())
    if structurally_ready and spec["audit_status"] == "explicitly_unaudited":
        status = "blocked_explicitly_unaudited"
    elif structurally_ready:
        status = "ready_for_supervised_execution"
    else:
        status = "not_ready"
    identity = {
        "case_id": negative_case["case_id"],
        "scope_role": spec["scope_role"],
        "global_headcount": global_headcount,
        "covered_headcount": covered_headcount,
        "excluded_headcount": excluded_headcount,
    }
    return {
        "schema_version": "0.1",
        "record_kind": "organizational_population_boundary_validation",
        "validation_id": stable_id("population-validation", identity),
        "case_id": negative_case["case_id"],
        "fact_record_id": fact["record_id"],
        "task_id": negative_case["task_id"],
        "predicate": negative_case["predicate"],
        "value": fact["value"],
        "resolved_population": {
            "scope_role": spec["scope_role"],
            "period": "2025 year-end",
            "worker_type": "employees",
            "global_headcount": global_headcount,
            "covered_headcount": covered_headcount,
            "excluded_headcount": excluded_headcount,
            "permanent_employees": permanent,
            "temporary_employees": temporary,
            "excluded_entity_reason": "newly acquired entities not yet implemented in SF",
            "audit_status": spec["audit_status"],
        },
        "checks": checks,
        "validation_status": status,
        "execution_performed": False,
        "promotion_performed": False,
        "rollback": "delete_validation_and_preserve_unresolved_candidate",
    }


def validate_target_performance_case(
    negative_case: dict[str, Any],
    fact: dict[str, Any],
    native_binding: dict[str, Any],
    root: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Separate target commitments from achieved performance and comparators."""
    native_text = "\n".join(
        item.get("context", "") for item in native_binding.get("candidates", [])
    ).casefold()
    evidence_text = "\n".join(item.get("quote", "") for item in fact.get("evidence", [])).casefold()
    supporting_text = str(spec.get("supporting_context", "")).casefold()
    combined = f"{native_text}\n{supporting_text}\n{evidence_text}"
    metadata = fact["subject"].get("document_metadata", [])
    source_hash_valid = bool(metadata) and all(
        (root / item["local_path"]).is_file()
        and sha256_file(root / item["local_path"]) == item["sha256"]
        for item in metadata
    )
    required_phrases_present = all(
        phrase.casefold() in combined for phrase in spec["required_phrases"]
    )
    forbidden_phrases_absent = all(
        phrase.casefold() not in spec["resolved_relation"].casefold()
        for phrase in spec.get("forbidden_relation_phrases", [])
    )
    role = spec["claim_role"]
    role_language_present = (role == "target" and "target" in combined) or (
        role == "achieved_performance"
        and any(marker in combined for marker in ("in 2025", "this is a decrease", "reduced"))
    )
    checks = {
        "source_document_hash_valid": source_hash_valid,
        "unique_native_binding": native_binding.get("status") == "unique_context_binding",
        "literal_in_native_context": str(fact["value"]).casefold() in native_text,
        "required_relation_phrases_present": required_phrases_present,
        "claim_role_valid": role in {"target", "achieved_performance"},
        "claim_role_language_present": role_language_present,
        "target_year_bound": spec.get("target_year") is None
        or str(spec["target_year"]) in combined,
        "performance_year_bound": spec.get("performance_year") is None
        or str(spec["performance_year"]) in combined,
        "baseline_or_comparator_bound": spec["baseline_relation"].casefold() in combined
        and str(spec["baseline_or_comparator"]) in spec["baseline_relation"],
        "metric_scope_bound": all(
            marker.casefold() in combined for marker in spec["metric_scope_markers"]
        ),
        "resolved_relation_specific": bool(spec["resolved_relation"]),
        "competing_relation_excluded": forbidden_phrases_absent,
        "predicate_value_matches_relation": fact["value"] == spec["expected_value"],
        "unit_is_percentage": spec["unit"] == "percent",
        "audit_status_explicit": spec["audit_status"]
        in {"pending_independent_scope_review", "explicitly_unaudited"},
    }
    structurally_ready = all(checks.values())
    if structurally_ready and spec["audit_status"] == "explicitly_unaudited":
        status = "blocked_explicitly_unaudited"
    elif structurally_ready:
        status = "ready_for_supervised_execution"
    else:
        status = "not_ready"
    identity = {
        "case_id": negative_case["case_id"],
        "claim_role": role,
        "resolved_relation": spec["resolved_relation"],
    }
    return {
        "schema_version": "0.1",
        "record_kind": "target_performance_boundary_validation",
        "validation_id": stable_id("target-performance-validation", identity),
        "case_id": negative_case["case_id"],
        "fact_record_id": fact["record_id"],
        "task_id": negative_case["task_id"],
        "predicate": negative_case["predicate"],
        "value": fact["value"],
        "resolved_claim": {
            "claim_role": role,
            "metric": spec["metric"],
            "unit": spec["unit"],
            "target_year": spec.get("target_year"),
            "performance_year": spec.get("performance_year"),
            "baseline_or_comparator": spec["baseline_or_comparator"],
            "scope_boundary": spec["scope_boundary"],
            "resolved_relation": spec["resolved_relation"],
            "audit_status": spec["audit_status"],
        },
        "checks": checks,
        "validation_status": status,
        "execution_performed": False,
        "promotion_performed": False,
        "rollback": "delete_validation_and_preserve_unresolved_candidate",
    }
