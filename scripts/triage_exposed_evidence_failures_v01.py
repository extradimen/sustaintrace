from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.evidence_repair_triage import plan_evidence_repair
from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
TARGET_SIGNATURES = {
    "EVIDENCE_GROUNDING_MISMATCH",
    "EVIDENCE_SELECTION_GAP",
    "TARGET_ASSURANCE_WINDOW_INCOMPLETE",
}


def main() -> None:
    failures_path = KB / "failure_records.jsonl"
    failures = [
        json.loads(line)
        for line in failures_path.read_text().splitlines()
        if line and json.loads(line)["failure_signature"] in TARGET_SIGNATURES
    ]
    plans = [plan_evidence_repair(item, mode="locked_evaluation") for item in failures]
    schema_path = ROOT / "schemas/knowledge/evidence-repair-triage-v0.1.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    errors = [error.message for item in plans for error in validator.iter_errors(item)]
    if errors:
        raise ValueError(f"triage schema validation failed: {errors[:3]}")

    output_path = KB / "exposed_evidence_failure_triage.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in plans
        )
    )
    subtype_counts = Counter(item["causal_subtype"] for item in plans)
    result = {
        "schema_version": "0.1",
        "audit_id": "ESG-EVIDENCE-REPAIR-TRIAGE-v0.1",
        "status": "exposed_failures_subtyped_locked_results_archive_only",
        "failure_records_triaged": len(plans),
        "causal_subtype_counts": dict(sorted(subtype_counts.items())),
        "locked_evaluation_decisions": dict(Counter(item["decision"] for item in plans)),
        "operational_router_implemented": True,
        "execution_performed": False,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            str(failures_path.relative_to(ROOT)): sha256_file(failures_path),
            str(schema_path.relative_to(ROOT)): sha256_file(schema_path),
        },
        "output": {
            "path": str(output_path.relative_to(ROOT)),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "build frozen operational validation contracts for each causal subtype",
    }
    result_path = ROOT / "data/results/evidence_repair_triage_v0.1.lock.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["causal_subtype_counts"], sort_keys=True))


if __name__ == "__main__":
    main()
