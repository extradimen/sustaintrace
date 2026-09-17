from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import validate

from esg_reliable_discovery.knowledge_query import query_control_plane

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
CATALOG = ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    response_schema_path = ROOT / "schemas/knowledge/control-plane-query-response-v0.1.schema.json"
    lifecycle_schema_path = (
        ROOT / "schemas/knowledge/repair-lifecycle-query-response-v0.1.schema.json"
    )
    response = query_control_plane(
        KB,
        CATALOG,
        include_candidates=False,
        include_regression_observations=True,
    )
    validate(response, json.loads(response_schema_path.read_text(encoding="utf-8")))
    validate(
        response["repairs"],
        json.loads(lifecycle_schema_path.read_text(encoding="utf-8")),
    )

    executions = response["repairs"]["executions"]
    successful = [
        item for item in executions
        if item["effective_outcome"] == "successful_validated_repair"
    ]
    negative = [
        item for item in executions
        if item["effective_outcome"] == "not_a_successful_repair"
    ]
    if len(successful) != 1 or len(negative) != 3:
        raise RuntimeError("repair lifecycle outcome partition is inconsistent")
    if any(
        item["execution"]["state"] in {"rolled_back", "blocked_preflight"}
        and item["effective_outcome"] != "not_a_successful_repair"
        for item in executions
    ):
        raise RuntimeError("negative repair outcome was exposed as success")

    artifacts = [
        ROOT / "src/esg_reliable_discovery/knowledge_query.py",
        ROOT / "src/esg_reliable_discovery/repair_execution.py",
        response_schema_path,
        lifecycle_schema_path,
        KB / "fact_records.jsonl",
        KB / "trusted_fact_records.jsonl",
        KB / "failure_records.jsonl",
        KB / "repair_execution_states.jsonl",
        KB / "repair_execution_events.jsonl",
        CATALOG,
    ]
    output = {
        "schema_version": "0.1",
        "status": "control_plane_query_interface_passed",
        "facts": response["facts"]["inventory"],
        "repairs": response["repairs"]["inventory"],
        "successful_validated_repairs_exposed": len(successful),
        "negative_repair_outcomes_preserved": len(negative),
        "regression_observations_visible_by_explicit_opt_in": True,
        "read_only_interface": True,
        "locked_experiments_modified_or_rescored": False,
        "artifacts": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in artifacts
        },
        "next_gate": "connect policy-selected repair actions to the execution state machine",
    }
    output_path = ROOT / "data/results/control_plane_query_v01_audit.lock.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
