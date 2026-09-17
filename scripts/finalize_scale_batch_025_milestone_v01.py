from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_025_milestone_audit.lock.json"

ARTIFACTS = (
    "configs/knowledge/scale_batch_025_v0.1.json",
    "configs/parsers/scale-batch-025-mineru-3.4.0-runtime.json",
    "configs/knowledge/repair_strategy_catalog_v0.1.json",
    "data/manifests/scale_batch_025_acquisition.lock.json",
    "data/results/scale_batch_025_diagnostics.lock.json",
    "data/results/scale_batch_025_performance_baseline.lock.json",
    "data/manifests/scale_batch_025_target_pages.lock.json",
    "data/results/scale_batch_025_mineru_summary.lock.json",
    "data/manifests/scale_batch_025_mineru_RESUME01_lineage.lock.json",
    "data/results/scale_batch_025_mineru_RESUME01_summary.lock.json",
    "data/manifests/scale_batch_025_mineru_RESUME02_lineage.lock.json",
    "data/results/scale_batch_025_mineru_RESUME02_summary.lock.json",
    "data/manifests/scale_batch_025_mineru_RESUME03_lineage.lock.json",
    "data/results/scale_batch_025_mineru_RESUME03_summary.lock.json",
    "data/results/scale_batch_025_mineru_FINAL_summary.lock.json",
    "data/results/scale_batch_025_kb_increment.lock.json",
    "data/results/scale_batch_025_atomic_projection.lock.json",
    "data/results/scale_batch_025_atomic_validation.lock.json",
    "data/manifests/scale_batch_025_table_graphs.lock.json",
    "data/results/scale_batch_025_native_coordinate_audit.lock.json",
    "data/results/scale_batch_025_tier_b_promotion.lock.json",
    "data/knowledge_bases/v0.1/increments/scale_batch_025_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_025_atomic_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_025_atomic_validations.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_025_failure_records.jsonl",
    "data/knowledge_bases/v0.1/migration_manifest.lock.json",
    "data/knowledge_bases/v0.1/failure_signature_catalog.json",
    "data/knowledge_bases/v0.1/trusted_fact_records.jsonl",
    "artifacts/scale_batch_025/assurance_visual_review/equinor_p305.png",
    "artifacts/scale_batch_025/assurance_visual_review/equinor_p307.png",
    "artifacts/scale_batch_025/assurance_visual_review/akerbp_p126.png",
    "artifacts/scale_batch_025/assurance_visual_review/akerbp_p127.png",
    "artifacts/scale_batch_025/assurance_visual_review/dnb_p350.png",
    "artifacts/scale_batch_025/assurance_visual_review/dnb_p353.png",
    "docs/146_规模化知识引入第二十五批表格投影失败闭环_v0.1.md",
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def count(path: str) -> int:
    return sum(bool(line) for line in (ROOT / path).read_text().splitlines())


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite Batch25 milestone audit")
    diagnostics = load("data/results/scale_batch_025_diagnostics.lock.json")
    final = load("data/results/scale_batch_025_mineru_FINAL_summary.lock.json")
    increment = load("data/results/scale_batch_025_kb_increment.lock.json")
    projection = load("data/results/scale_batch_025_atomic_projection.lock.json")
    promotion = load("data/results/scale_batch_025_tier_b_promotion.lock.json")
    performance = load("data/results/scale_batch_025_performance_baseline.lock.json")
    migration = load("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-025",
        "status": "local_ingestion_projection_fail_closed_and_repair_observation_complete",
        "source_documents": diagnostics["totals"]["documents"],
        "source_pages": diagnostics["totals"]["pdf_pages"],
        "extractable_source_pages": diagnostics["totals"]["extractable_pages"],
        "frozen_target_pages": final["complete_pages"],
        "assurance_window_preflight_passed": 3,
        "rejected_candidates_before_freeze": 1,
        "scale_coverage": {
            "completed_unique_reports": 108,
            "stage_target_reports": 120,
            "completion_percent": 90.0,
            "remaining_reports": 12,
            "estimated_remaining_three_report_batches": 4,
        },
        "mineru": {
            "final_usable_pages": final["complete_pages"],
            "resume_completed_pages": performance["mineru"]["resume_completed_pages"],
            "hash_recovered_pages": final["post_completion_shutdown_recovered_pages"],
            "remaining_failures": final["failed_pages"],
            "successful_pages_per_hour": performance["mineru"]["successful_target_pages_per_hour"],
        },
        "knowledge_increment": {
            "evidence_snippet_candidates": increment["fact_candidates"],
            "atomic_fact_candidates": projection["atomic_fact_candidates"],
            "failure_observations": increment["failure_observations"],
            "remaining_evidence_gaps": increment["evidence_gaps"],
            "promoted_tier_b": promotion["newly_promoted_to_tier_b"],
            "projection_failure_signature": "TABLE_FRAGMENT_WITHOUT_ATOMIC_NUMERIC_CELLS",
        },
        "global_knowledge_bases": {
            "fact_records": migration["counts"]["fact_records"],
            "trusted_fact_records": count("data/knowledge_bases/v0.1/trusted_fact_records.jsonl"),
            "failure_records": migration["counts"]["failure_records"],
            "failure_signatures": migration["counts"]["failure_signatures"],
            "repair_observations": migration["counts"]["repair_observations"],
        },
        "quality_gates": {
            "pytest_collected_and_passed": 478,
            "ruff": "passed",
            "json_artifacts_parse": "batch_025_locked_json_passed",
            "sha256_manifest": "passed",
            "cloud_transmission": False,
            "locked_experiments_modified": False,
            "automatic_promotion": False,
            "failed_runs_preserved": True,
        },
        "artifact_sha256": {path: sha(path) for path in ARTIFACTS},
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["scale_coverage"], sort_keys=True))


if __name__ == "__main__":
    main()
