from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_dispatch import index_executors, prepare_execution_request

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    plans = {item["plan_id"]: item for item in load_jsonl(KB / "repair_controller_dry_run.jsonl")}
    validations = load_jsonl(KB / "automatic_candidate_validations.jsonl")
    strategy_path = ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json"
    executor_path = ROOT / "configs/knowledge/repair_executor_catalog_v0.1.json"
    strategies = {
        item["strategy_id"]: item
        for item in json.loads(strategy_path.read_text())["strategies"]
    }
    executors = index_executors(json.loads(executor_path.read_text()))

    decisions = []
    for validation in validations:
        plan = plans[validation["plan_id"]]
        strategy = strategies[validation["strategy_id"]]
        decisions.append(
            prepare_execution_request(
                plan,
                validation,
                strategy,
                executors.get(strategy["strategy_id"]),
                ROOT,
            )
        )

    decision_path = KB / "repair_dispatch_decisions.jsonl"
    decision_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in decisions
        ),
        encoding="utf-8",
    )
    reasons = Counter(
        reason for decision in decisions for reason in decision["blocking_reasons"]
    )
    summary = {
        "schema_version": "0.1",
        "status": "repair_dispatch_gate_audited",
        "automatic_candidates": len(decisions),
        "ready_for_execution": sum(
            item["decision"] == "ready_for_execution" for item in decisions
        ),
        "blocked": sum(item["decision"] == "blocked" for item in decisions),
        "blocking_reason_counts": dict(sorted(reasons.items())),
        "execution_started": 0,
        "locked_experiments_modified_or_rescored": False,
        "artifacts": {
            "decisions": {
                "path": decision_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(decision_path),
            },
            "strategy_catalog_sha256": sha256_file(strategy_path),
            "executor_catalog_sha256": sha256_file(executor_path),
        },
        "next_gate": "freeze action-specific input and expected-output contracts",
    }
    summary_path = KB / "repair_dispatch_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
