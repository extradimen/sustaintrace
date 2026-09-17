from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records
from esg_reliable_discovery.repair_controller import index_strategies, plan_repair

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    kb_dir = ROOT / "data/knowledge_bases/v0.1"
    failure_path = kb_dir / "failure_records.jsonl"
    strategy_path = ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json"
    failures = load_jsonl(failure_path)
    catalog = json.loads(strategy_path.read_text())
    strategies = index_strategies(catalog)
    plans = [plan_repair(failure, strategies, mode="operational") for failure in failures]
    schema = json.loads((ROOT / "schemas/knowledge/repair-plan-v0.1.schema.json").read_text())
    validate_records(plans, schema)

    plan_path = kb_dir / "repair_controller_dry_run.jsonl"
    plan_path.write_text(
        "".join(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for plan in plans
        ),
        encoding="utf-8",
    )
    decisions: dict[str, int] = {}
    for plan in plans:
        decisions[plan["decision"]] = decisions.get(plan["decision"], 0) + 1
    summary = {
        "schema_version": "0.1",
        "status": "dry_run_complete_no_repairs_executed",
        "mode": "operational",
        "failure_records": len(failures),
        "decision_counts": decisions,
        "execution_count": 0,
        "locked_experiments_modified": False,
        "inputs": {
            "failures_sha256": sha256_file(failure_path),
            "strategies_sha256": sha256_file(strategy_path),
        },
        "output": {
            "path": "data/knowledge_bases/v0.1/repair_controller_dry_run.jsonl",
            "sha256": sha256_file(plan_path),
        },
        "next_gate": "implement validators and rollback ledger for automatic candidates",
    }
    summary_path = kb_dir / "repair_controller_dry_run_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decisions, sort_keys=True))


if __name__ == "__main__":
    main()
