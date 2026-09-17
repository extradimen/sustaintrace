from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_controller import (
    index_strategies,
    validate_automatic_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    kb_dir = ROOT / "data/knowledge_bases/v0.1"
    failures = {item["record_id"]: item for item in load_jsonl(kb_dir / "failure_records.jsonl")}
    plans = load_jsonl(kb_dir / "repair_controller_dry_run.jsonl")
    catalog_path = ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json"
    catalog = json.loads(catalog_path.read_text())
    strategies_by_signature = index_strategies(catalog)
    strategies_by_id = {
        strategy["strategy_id"]: strategy for strategy in catalog["strategies"]
    }
    candidates = [plan for plan in plans if plan["decision"] == "automatic_candidate"]
    validations = [
        validate_automatic_candidate(
            plan,
            failures[plan["failure_record_id"]],
            strategies_by_id[plan["strategy_id"]],
            ROOT,
        )
        for plan in candidates
    ]
    if len(strategies_by_signature) < 1:
        raise ValueError("repair strategy index is empty")
    output_path = kb_dir / "automatic_candidate_validations.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in validations
        ),
        encoding="utf-8",
    )
    ready = sum(item["validation_status"] == "ready_not_executed" for item in validations)
    summary = {
        "schema_version": "0.1",
        "status": "automatic_candidate_validation_complete_no_execution",
        "candidate_count": len(validations),
        "ready_not_executed": ready,
        "not_ready": len(validations) - ready,
        "execution_count": 0,
        "rollback_ledgers_prepared": len(validations),
        "strategy_catalog_sha256": sha256_file(catalog_path),
        "output": {
            "path": "data/knowledge_bases/v0.1/automatic_candidate_validations.jsonl",
            "sha256": sha256_file(output_path),
        },
        "next_gate": "execute only in a new operational run with immutable parent lineage",
    }
    summary_path = kb_dir / "automatic_candidate_validation_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ready_not_executed": ready, "not_ready": len(validations) - ready}))


if __name__ == "__main__":
    main()
