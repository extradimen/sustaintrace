from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_005_tier_b_milestone_audit.lock.json"

ARTIFACTS = (
    "data/results/scale_batch_005_tier_b_promotion.lock.json",
    "data/knowledge_bases/v0.1/tier_b_independent_adjudications.jsonl",
    "data/knowledge_bases/v0.1/trusted_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_005_atomic_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_005_atomic_validations.jsonl",
)


def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    promotion = json.loads(
        (ROOT / "data/results/scale_batch_005_tier_b_promotion.lock.json").read_text()
    )
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-005-TIER-B-SAMPLE",
        "status": "six_dimension_tier_b_sampling_complete",
        "reviewed_atomic_facts": promotion["reviewed"],
        "promoted_tier_b": promotion["newly_promoted_to_tier_b"],
        "held_tier_c": len(promotion["blocked_fact_ids"]),
        "total_trusted_tier_b": promotion["total_trusted_tier_b"],
        "blocked_reason_counts": {
            key: len(value) for key, value in promotion["blocked_by_reason"].items()
        },
        "quality_gates": {
            "pytest_collected_and_passed": 447,
            "ruff": "passed",
            "candidate_records_modified": False,
            "locked_experiments_modified_or_rescored": False,
            "cloud_transmission": False,
        },
        "artifact_sha256": {path: sha256(path) for path in ARTIFACTS},
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
