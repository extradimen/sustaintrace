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
    schema_path = ROOT / "schemas/knowledge/control-plane-query-response-v0.1.schema.json"
    lifecycle_path = ROOT / "schemas/knowledge/repair-lifecycle-query-response-v0.1.schema.json"
    response = query_control_plane(
        KB,
        CATALOG,
        include_regression_observations=True,
    )
    validate(response, json.loads(schema_path.read_text()))
    validate(response["repairs"], json.loads(lifecycle_path.read_text()))
    repairs = response["repairs"]
    if repairs["inventory"]["dispatch_decisions"] != 4:
        raise RuntimeError("dispatch decisions missing from control-plane response")
    if repairs["inventory"]["dispatch_ready"] != 0:
        raise RuntimeError("unfrozen repair was made executable")
    if any(item["execution_started"] for item in repairs["dispatch_decisions"]):
        raise RuntimeError("dispatch audit observed an unapproved execution")

    inputs = [
        ROOT / "src/esg_reliable_discovery/knowledge_query.py",
        ROOT / "src/esg_reliable_discovery/repair_dispatch.py",
        ROOT / "configs/knowledge/repair_executor_catalog_v0.1.json",
        KB / "repair_dispatch_decisions.jsonl",
        KB / "repair_execution_states.jsonl",
        KB / "trusted_fact_records.jsonl",
    ]
    output = {
        "schema_version": "0.2",
        "status": "control_plane_with_dispatch_gate_passed",
        "fact_inventory": response["facts"]["inventory"],
        "repair_inventory": repairs["inventory"],
        "dispatch_policy": "missing_frozen_action_contract_blocks_execution",
        "execution_started_by_dispatch": 0,
        "locked_experiments_modified_or_rescored": False,
        "artifacts": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in inputs
        },
        "next_gate": "freeze an operational input-output contract for an eligible new repair",
    }
    path = ROOT / "data/results/control_plane_query_v02_audit.lock.json"
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
