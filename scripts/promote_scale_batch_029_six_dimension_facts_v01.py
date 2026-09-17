from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATOMIC = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_029_atomic_fact_records.jsonl"
VALIDATIONS = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_029_atomic_validations.jsonl"
AUDIT = ROOT / "data/results/scale_batch_029_native_coordinate_audit.lock.json"
SUMMARY = ROOT / "data/results/scale_batch_029_tier_b_promotion.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if AUDIT.exists() or SUMMARY.exists():
        raise RuntimeError("refusing to overwrite Batch29 promotion review")
    atomic = [line for line in ATOMIC.read_text().splitlines() if line]
    validations = [line for line in VALIDATIONS.read_text().splitlines() if line]
    if atomic or validations:
        raise ValueError("fail-closed: expected empty atomic promotion partition")
    audit = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-029-NATIVE-COORDINATE-AUDIT",
        "status": "no_atomic_cells_available_for_native_coordinate_review",
        "promotable_facts": 0,
        "checks": {},
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    trusted = ROOT / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_029_six_dimension_tier_b_review_complete_fail_closed",
        "reviewed": 0,
        "newly_promoted_to_tier_b": 0,
        "promotable_fact_ids": [],
        "blocked_fact_ids": [],
        "blocked_by_reason": {
            "no_deterministically_projectable_atomic_table_cells": []
        },
        "total_trusted_tier_b": sum(bool(x) for x in trusted.read_text().splitlines()),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha(ATOMIC),
            "atomic_validations_sha256": sha(VALIDATIONS),
            "native_coordinate_audit_sha256": sha(AUDIT),
        },
        "policy": {
            "promotion_requires_six_dimension_native_and_assurance_match": True,
            "empty_partition_is_valid_fail_closed_outcome": True,
            "cloud_transmission": False,
            "automatic_promotion": False,
        },
        "next_gate": "scale_batch_029_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
