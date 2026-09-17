from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.failure_prioritization import (
    lane_totals,
    summarize_failure_signatures,
)
from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    failures_path = KB / "failure_records.jsonl"
    catalog_path = ROOT / "configs/knowledge/repair_strategy_catalog_v0.1.json"
    schema_path = ROOT / "schemas/knowledge/failure-signature-priority-v0.1.schema.json"
    failures = load_jsonl(failures_path)
    catalog = json.loads(catalog_path.read_text())
    priorities = summarize_failure_signatures(failures, catalog)
    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    errors = [error.message for item in priorities for error in validator.iter_errors(item)]
    if errors:
        raise ValueError(f"priority schema validation failed: {errors[:3]}")

    output_path = KB / "failure_signature_priorities.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in priorities
        )
    )
    totals = lane_totals(failures)
    capability = [item for item in priorities if item["lane"] == "knowledge_capability"]
    result = {
        "schema_version": "0.1",
        "audit_id": "ESG-FAILURE-DRIVEN-REPAIR-PHASE-1-v0.1",
        "status": "failure_corpus_triaged_and_capability_queue_frozen",
        "scope": {
            "failure_records": len(failures),
            "failure_signatures": len(priorities),
            "lane_observations": totals,
            "capability_signatures": len(capability),
        },
        "priority_method": {
            "raw_frequency_is_not_capability_priority": True,
            "infrastructure_events_are_retained_but_zero_scored": True,
            "ranking_inputs": [
                "failure category impact",
                "affected experiment breadth",
                "bounded raw observations",
                "strategy maturity gap",
                "risk penalty",
            ],
        },
        "top_capability_queue": capability[:5],
        "inputs": {
            str(failures_path.relative_to(ROOT)): sha256_file(failures_path),
            str(catalog_path.relative_to(ROOT)): sha256_file(catalog_path),
            str(schema_path.relative_to(ROOT)): sha256_file(schema_path),
        },
        "output": {
            "path": str(output_path.relative_to(ROOT)),
            "sha256": sha256_file(output_path),
        },
        "locked_experiments_modified_or_rescored": False,
        "next_gate": "implement top capability workstream on exposed failures only",
    }
    result_path = ROOT / "data/results/failure_driven_repair_phase_1_audit.lock.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "records": len(failures),
                "lanes": totals,
                "top": [item["failure_signature"] for item in capability[:5]],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
