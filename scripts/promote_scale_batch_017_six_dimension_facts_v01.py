from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_017_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_017_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_017_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_017_native_coordinate_audit.lock.json"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    candidates = load_jsonl(INCREMENT)
    validations = load_jsonl(VALIDATIONS)
    if candidates or validations:
        raise ValueError("fail-closed: Batch17 atomic inventory unexpectedly non-empty")
    trusted_path = KB / "trusted_fact_records.jsonl"
    trusted_count = len(load_jsonl(trusted_path))
    audit = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-017-NATIVE-COORDINATE-AUDIT",
        "status": "no_atomic_cells_available_for_native_coordinate_review",
        "promotable_facts": 0,
        "checks": {
            "atomic_inventory_empty": True,
            "fail_closed_without_semantic_reconstruction": True,
        },
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_017_six_dimension_tier_b_review_complete_no_candidates",
        "reviewed": 0,
        "newly_promoted_to_tier_b": 0,
        "promotable_fact_ids": [],
        "blocked_fact_ids": [],
        "blocked_by_reason": {
            "no_unambiguous_two_axis_cells_from_frozen_candidates": []
        },
        "total_trusted_tier_b": trusted_count,
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha256_file(INCREMENT),
            "atomic_validations_sha256": sha256_file(VALIDATIONS),
            "native_coordinate_audit_sha256": sha256_file(NATIVE_AUDIT),
        },
        "outputs": {
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "native_audit": audit,
        "next_gate": "scale_batch_017_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
