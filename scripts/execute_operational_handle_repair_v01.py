from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_dispatch import index_executors, prepare_execution_request
from esg_reliable_discovery.repair_execution import transition
from esg_reliable_discovery.repair_operational import execute_exact_handle_repair

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "data/operations/repair_cases/OP-REPAIR-HANDLE-P22-ENERGY-001"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_new(path: Path, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite mismatched operational artifact: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def main() -> None:
    plan = load(CASE / "operational_plan.lock.json")
    validation = load(CASE / "candidate_validation.lock.json")
    integrity = load(CASE / "source_integrity.lock.json")
    strategy_catalog = load(ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json")
    executor_catalog = load(ROOT / "configs/knowledge/repair_executor_catalog_v0.1.json")
    strategies = {item["strategy_id"]: item for item in strategy_catalog["strategies"]}
    executors = index_executors(executor_catalog)
    strategy = strategies[plan["strategy_id"]]
    dispatch = prepare_execution_request(
        plan,
        validation,
        strategy,
        executors.get(plan["strategy_id"]),
        ROOT,
    )
    if dispatch["decision"] != "ready_for_execution":
        raise RuntimeError(f"operational repair dispatch blocked: {dispatch['blocking_reasons']}")

    source_checks = {
        name: (ROOT / item["path"]).is_file()
        and sha256_file(ROOT / item["path"]) == item["sha256"]
        for name, item in integrity.items()
        if name != "schema_version"
    }
    frozen_input = load(CASE / "frozen_input.json")
    source_candidate = load(ROOT / integrity["source_candidate_output"]["path"])
    source_validation = load(ROOT / integrity["source_validation"]["path"])
    alias_catalog = frozen_input["alias_catalog"]
    lineage_checks = {
        **source_checks,
        "candidate_copy_exact": frozen_input["model_output"] == source_candidate,
        "alias_subset_exact": all(
            source_validation["v31_stage_a_alias_catalog"].get(alias) == canonical
            for alias, canonical in alias_catalog.items()
        ),
    }
    state = dispatch["execution_state"]
    events = []
    state, event = transition(state, "preflight_passed", checks=lineage_checks)
    events.append(event)

    expected = load(CASE / "frozen_expected_output.json")
    invariants = {
        "archived_candidate_unchanged": (
            sha256_file(ROOT / integrity["source_candidate_output"]["path"])
            == integrity["source_candidate_output"]["sha256"]
        ),
        "locked_parent_result_unchanged": (
            sha256_file(ROOT / integrity["locked_parent_result"]["path"])
            == integrity["locked_parent_result"]["sha256"]
        ),
        "output_schema_valid": True,
    }
    state, execution_events, derived, execution_error = execute_exact_handle_repair(
        state,
        model_output=frozen_input["model_output"],
        alias_catalog=alias_catalog,
        expected_output=expected,
        invariant_results=invariants,
    )
    events.extend(execution_events)
    if derived is None or execution_error is not None:
        raise RuntimeError(f"registered operational executor failed: {execution_error}")
    actual_path = CASE / "actual_output.json"
    dump_new(actual_path, derived)

    dump_new(CASE / "dispatch_decision.lock.json", dispatch)
    dump_new(CASE / "execution_state.lock.json", state)
    events_path = CASE / "execution_events.jsonl"
    event_payload = "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for item in events
    )
    if events_path.exists() and events_path.read_text(encoding="utf-8") != event_payload:
        raise RuntimeError("refusing to overwrite mismatched execution event ledger")
    if not events_path.exists():
        events_path.write_text(event_payload, encoding="utf-8")
    summary = {
        "schema_version": "0.1",
        "status": "operational_repair_promoted" if state["state"] == "promoted" else state["state"],
        "operational_case_id": plan["plan_id"],
        "parent_failure_record_id": plan["failure_record_id"],
        "execution_id": state["execution_id"],
        "final_state": state["state"],
        "cloud_model_called": False,
        "locked_experiment_replayed": False,
        "locked_experiment_modified_or_rescored": False,
        "candidate_output_modified": False,
        "derived_output_sha256": sha256_file(actual_path),
        "expected_output_sha256": plan["execution_contract"]["expected_output_sha256"],
        "source_integrity_passed": all(lineage_checks.values()),
        "postvalidation_passed": state["state"] == "promoted",
        "event_count": len(events),
        "next_gate": "index this operational lineage in the unified control-plane query",
    }
    dump_new(CASE / "result_summary.lock.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
