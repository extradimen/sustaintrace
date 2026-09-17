from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import validate

from esg_reliable_discovery.knowledge_query import query_control_plane

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
CATALOG = ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json"
CASE = ROOT / "data/operations/repair_cases/OP-REPAIR-HANDLE-P22-ENERGY-001"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    schema_path = ROOT / "schemas/knowledge/control-plane-query-response-v0.1.schema.json"
    lifecycle_path = ROOT / "schemas/knowledge/repair-lifecycle-query-response-v0.1.schema.json"
    response = query_control_plane(
        KB,
        CATALOG,
        include_regression_observations=True,
    )
    validate(response, json.loads(schema_path.read_text()))
    validate(response["repairs"], json.loads(lifecycle_path.read_text()))
    inventory = response["repairs"]["inventory"]
    if inventory["repair_executions"] != 5 or inventory["dispatch_ready"] != 1:
        raise RuntimeError("operational repair lineage is absent from the control plane")
    operational = [
        item
        for item in response["repairs"]["executions"]
        if item["source_artifact"].startswith("data/operations/repair_cases/")
    ]
    if len(operational) != 1:
        raise RuntimeError("operational repair lineage count is not exactly one")
    if operational[0]["effective_outcome"] != "successful_validated_repair":
        raise RuntimeError("validated operational repair was not exposed as successful")

    inputs = [
        ROOT / "src/esg_reliable_discovery/knowledge_query.py",
        CASE / "operational_plan.lock.json",
        CASE / "frozen_input.json",
        CASE / "frozen_expected_output.json",
        CASE / "actual_output.json",
        CASE / "execution_state.lock.json",
        CASE / "execution_events.jsonl",
        CASE / "result_summary.lock.json",
    ]
    output = {
        "schema_version": "0.3",
        "status": "operational_repair_indexed_in_control_plane",
        "fact_inventory": response["facts"]["inventory"],
        "repair_inventory": inventory,
        "operational_repair_executions": 1,
        "operational_repair_promotions": 1,
        "cloud_model_called": False,
        "locked_experiment_replayed": False,
        "locked_experiments_modified_or_rescored": False,
        "artifacts": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in inputs
        },
        "next_gate": "add isolated executor failure rollback and idempotency regression cases",
    }
    path = ROOT / "data/results/control_plane_query_v03_audit.lock.json"
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
