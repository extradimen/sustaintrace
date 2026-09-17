from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from esg_reliable_discovery.knowledge_base import stable_id

_PERIOD_REASONS = {"PERIOD_BINDING_AMBIGUOUS", "PERIOD_BINDING_MISSING"}
_UNIT_REASONS = {"UNIT_BINDING_AMBIGUOUS", "UNIT_BINDING_MISSING"}


def _controlled_unit(value: Any) -> str | None:
    literal = " ".join(str(value or "").split())
    rules = (
        ("percent", r"^(?:%|percent(?:age)?)$"),
        ("tCO2e", r"^(?:tco2e|tonnes?\s+of\s+co2e)$"),
        ("m3", r"^(?:m3|cubic\s+met(?:er|re)s)$"),
        ("MWh", r"^mwh$"),
        ("GWh", r"^gwh$"),
        ("TWh", r"^twh$"),
        ("FTE", r"^(?:fte|full[- ]time equivalent)$"),
        ("people", r"^(?:employees?|people|headcount)$"),
        ("hours", r"^hours?$"),
    )
    return next(
        (canonical for canonical, pattern in rules if re.fullmatch(pattern, literal, re.I)),
        None,
    )


def execute_unique_table_bindings(
    *,
    facts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    dispatches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Derive job-local facts only when one exact table cell binds the value and period."""
    candidate_index = {item["record_id"]: item for item in candidates}
    plan_index = {item["fact_record_id"]: item for item in plans}
    dispatch_index = {item["fact_record_id"]: item for item in dispatches}
    derived_facts: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []

    for fact in facts:
        fact_id = fact["record_id"]
        plan = plan_index.get(fact_id)
        dispatch = dispatch_index.get(fact_id)
        candidate = candidate_index.get(fact.get("subject", {}).get("task_id"))
        if not plan or not dispatch or not candidate:
            continue
        trigger_reasons = {route["blocking_reason"] for route in plan.get("routes", [])}
        if not trigger_reasons.intersection(_PERIOD_REASONS | _UNIT_REASONS):
            continue
        if dispatch.get("decision") != "ready_for_supervised_execution":
            continue

        matches = []
        fact_value = str(fact.get("value"))
        for graph in candidate.get("table_graphs", []):
            if graph.get("status") != "two_axis_graph_built":
                continue
            for cell in graph.get("cells", []):
                if str(cell.get("normalized_value")) == fact_value:
                    matches.append(cell)
        identity = {
            "parent_fact_record_id": fact_id,
            "candidate_cell_handles": sorted(
                cell.get("cell_handle", "") for cell in matches
            ),
        }
        if len(matches) != 1:
            executions.append(
                {
                    "schema_version": "1.0",
                    "record_kind": "workbench_repair_execution",
                    "execution_id": stable_id("workbench-repair-execution", identity),
                    "repair_plan_id": plan["repair_plan_id"],
                    "dispatch_id": dispatch["dispatch_id"],
                    "parent_fact_record_id": fact_id,
                    "derived_fact_record_id": None,
                    "strategy_id": "RS-PARSER-FALLBACK",
                    "validator_id": "RV-TABLE-ROW-COLUMN-TOPOLOGY-V01",
                    "state": "rolled_back",
                    "checks": {
                        "source_frozen_hash_valid": True,
                        "exact_numeric_literal_match": bool(matches),
                        "unique_table_cell_match": False,
                        "parent_fact_unchanged": True,
                    },
                    "selected_cell": None,
                    "candidate_cell_handles": identity["candidate_cell_handles"],
                    "execution_performed": False,
                    "promotion_performed": False,
                    "trusted_layer_modified": False,
                    "cloud_transfer_performed": False,
                    "rollback_performed": True,
                    "rollback_action": "preserve parent fact and ambiguity evidence",
                }
            )
            continue

        cell = matches[0]
        bound_period = cell.get("normalized_period")
        bound_unit = _controlled_unit(cell.get("unit")) or fact["qualifiers"].get(
            "normalized_unit"
        )
        binding_checks = {
            "source_frozen_hash_valid": True,
            "exact_numeric_literal_match": True,
            "unique_table_cell_match": True,
            "explicit_period_header_bound": isinstance(bound_period, int),
            "controlled_unit_bound": bound_unit is not None,
            "parent_fact_unchanged": True,
        }
        if not all(binding_checks.values()):
            executions.append(
                {
                    "schema_version": "1.0",
                    "record_kind": "workbench_repair_execution",
                    "execution_id": stable_id("workbench-repair-execution", identity),
                    "repair_plan_id": plan["repair_plan_id"],
                    "dispatch_id": dispatch["dispatch_id"],
                    "parent_fact_record_id": fact_id,
                    "derived_fact_record_id": None,
                    "strategy_id": "RS-PARSER-FALLBACK",
                    "validator_id": "RV-TABLE-ROW-COLUMN-TOPOLOGY-V01",
                    "state": "rolled_back",
                    "checks": binding_checks,
                    "selected_cell": cell,
                    "candidate_cell_handles": [cell["cell_handle"]],
                    "execution_performed": False,
                    "promotion_performed": False,
                    "trusted_layer_modified": False,
                    "cloud_transfer_performed": False,
                    "rollback_performed": True,
                    "rollback_action": "preserve parent fact and incomplete binding evidence",
                }
            )
            continue

        derived = deepcopy(fact)
        identity = {
            "parent_fact_record_id": fact_id,
            "cell_handle": cell["cell_handle"],
            "period": bound_period,
            "unit": bound_unit,
        }
        derived["record_id"] = stable_id("fact", identity)
        derived["knowledge_status"] = "reference_candidate"
        derived["qualifiers"]["period_literal"] = cell["column_header"]
        derived["qualifiers"]["reference_period"] = bound_period
        derived["qualifiers"]["normalized_unit"] = bound_unit
        derived["qualifiers"]["answer_status"] = "repair_postvalidated"
        derived["evidence"][0].update(
            {
                "cell_handle": cell["cell_handle"],
                "table_index": cell["table_index"],
                "row_index": cell["row_index"],
                "column_index": cell["column_index"],
                "row_header": cell["row_header"],
                "column_header": cell["column_header"],
            }
        )
        derived["provenance"]["reference_status"] = (
            "workbench_deterministic_table_binding_repair"
        )
        derived_facts.append(derived)
        executions.append(
            {
                "schema_version": "1.0",
                "record_kind": "workbench_repair_execution",
                "execution_id": stable_id("workbench-repair-execution", identity),
                "repair_plan_id": plan["repair_plan_id"],
                "dispatch_id": dispatch["dispatch_id"],
                "parent_fact_record_id": fact_id,
                "derived_fact_record_id": derived["record_id"],
                "strategy_id": "RS-PARSER-FALLBACK",
                "validator_id": "RV-TABLE-ROW-COLUMN-TOPOLOGY-V01",
                "state": "postvalidation_passed",
                "checks": binding_checks,
                "selected_cell": cell,
                "candidate_cell_handles": [cell["cell_handle"]],
                "execution_performed": True,
                "promotion_performed": False,
                "trusted_layer_modified": False,
                "cloud_transfer_performed": False,
                "rollback_performed": False,
                "rollback_action": "delete derived fact and preserve parent fact and failure",
            }
        )
    return derived_facts, executions
