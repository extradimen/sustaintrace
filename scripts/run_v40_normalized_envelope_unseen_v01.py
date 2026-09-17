#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.postvalidation_attachment import (
    build_diagnostic_result_envelope,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/v40_normalized_envelope_unseen_v0.1.lock.json"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/v40_normalized_envelope_unseen_v0.1/result.lock.json"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_v40_unseen_result")
    manifest = json.loads(MANIFEST.read_text())
    source_path = ROOT / manifest["input"]["path"]
    if sha256_file(source_path) != manifest["input"]["sha256"]:
        raise ValueError("frozen_input_hash_mismatch")
    payload = json.loads(source_path.read_text())
    binding = manifest["parent_binding"]
    envelope = build_diagnostic_result_envelope(
        payload=payload,
        diagnostic_path=manifest["input"]["path"],
        parent_fact_id=binding["fact_record_id"],
        parent_gap_id=binding["gap_id"],
        case_id=binding["case_id"],
        root=ROOT,
    )
    registered_gaps = {
        json.loads(line)["gap_id"] for line in GAPS.read_text().splitlines() if line
    }
    attachment_applicable = binding["gap_id"] in registered_gaps
    observed = {
        "normalized_status": envelope["normalized_status"],
        "raw_payload_preserved": envelope["raw_payload"] == payload,
        "parent_hash_preserved": (
            envelope["parent_artifact"]["sha256"] == manifest["input"]["sha256"]
        ),
        "attachment_applicable": attachment_applicable,
        "promotion_eligible": False,
    }
    contract_passed = all(
        observed[key] == value for key, value in manifest["expected"].items()
    )
    result = {
        "schema_version": "0.1",
        "experiment_id": manifest["experiment_id"],
        "status": "completed",
        "attempt_count": 1,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST),
        "observed": observed,
        "contract_passed": contract_passed,
        "envelope": envelope,
        "attachment_generated": False,
        "historical_result_modified": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
        "cloud_transmission_performed": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"contract_passed": contract_passed, **observed}))


if __name__ == "__main__":
    main()
