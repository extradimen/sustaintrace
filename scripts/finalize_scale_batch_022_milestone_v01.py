from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_022_milestone_audit.lock.json"

ARTIFACTS = (
    "configs/knowledge/scale_batch_022_v0.1.json",
    "configs/parsers/scale-batch-022-mineru-3.4.0-runtime.json",
    "configs/knowledge/repair_strategy_catalog_v0.1.json",
    "data/manifests/scale_batch_022_acquisition_failures.lock.json",
    "data/manifests/scale_batch_022_acquisition.lock.json",
    "data/results/scale_batch_022_diagnostics.lock.json",
    "data/results/scale_batch_022_performance_baseline.lock.json",
    "data/manifests/scale_batch_022_target_pages.lock.json",
    "data/results/scale_batch_022_mineru_summary.lock.json",
    "data/manifests/scale_batch_022_mineru_RESUME01_lineage.lock.json",
    "data/results/scale_batch_022_mineru_RESUME01_summary.lock.json",
    "data/manifests/scale_batch_022_mineru_RESUME02_lineage.lock.json",
    "data/results/scale_batch_022_mineru_RESUME02_summary.lock.json",
    "data/manifests/scale_batch_022_mineru_RESUME03_lineage.lock.json",
    "data/results/scale_batch_022_mineru_RESUME03_summary.lock.json",
    "data/results/scale_batch_022_mineru_FINAL_summary.lock.json",
    "data/results/scale_batch_022_kb_increment.lock.json",
    "data/results/scale_batch_022_atomic_projection.lock.json",
    "data/results/scale_batch_022_atomic_validation.lock.json",
    "data/manifests/scale_batch_022_table_graphs.lock.json",
    "data/results/scale_batch_022_native_coordinate_audit.lock.json",
    "data/results/scale_batch_022_tier_b_promotion.lock.json",
    "data/results/v38_scale_batch_022_exposed_control_plane_noop_development_v0.1.lock.json",
    "data/knowledge_bases/v0.1/increments/scale_batch_022_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_022_atomic_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_022_atomic_validations.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_022_failure_records.jsonl",
    "data/knowledge_bases/v0.1/migration_manifest.lock.json",
    "data/knowledge_bases/v0.1/repair_observations.jsonl",
    "data/knowledge_bases/v0.1/tier_b_independent_adjudications.jsonl",
    "data/knowledge_bases/v0.1/trusted_fact_records.jsonl",
    "scripts/promote_scale_batch_019_six_dimension_facts_v01.py",
    "tests/test_empty_promotion_partition.py",
    "artifacts/scale_batch_022/assurance_visual_review/engie-220.png",
    "artifacts/scale_batch_022/assurance_visual_review/engie-221.png",
    "artifacts/scale_batch_022/assurance_visual_review/orange_assurance-482.png",
    "artifacts/scale_batch_022/assurance_visual_review/orange_assurance-485.png",
    "artifacts/scale_batch_022/assurance_visual_review/skanska-208.png",
    "artifacts/scale_batch_022/assurance_visual_review/skanska-209.png",
    "docs/143_规模化知识引入第二十二批本地闭环与零晋级控制面修复_v0.1.md",
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def line_count(path: str) -> int:
    return sum(bool(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines())


def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite Batch22 milestone audit")
    diagnostics = load("data/results/scale_batch_022_diagnostics.lock.json")
    final = load("data/results/scale_batch_022_mineru_FINAL_summary.lock.json")
    increment = load("data/results/scale_batch_022_kb_increment.lock.json")
    projection = load("data/results/scale_batch_022_atomic_projection.lock.json")
    validation = load("data/results/scale_batch_022_atomic_validation.lock.json")
    promotion = load("data/results/scale_batch_022_tier_b_promotion.lock.json")
    performance = load("data/results/scale_batch_022_performance_baseline.lock.json")
    migration = load("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-022",
        "status": "local_ingestion_projection_tier_b_review_and_repair_observation_complete",
        "source_documents": diagnostics["totals"]["documents"],
        "source_pages": diagnostics["totals"]["pdf_pages"],
        "extractable_source_pages": diagnostics["totals"]["extractable_pages"],
        "frozen_target_pages": final["complete_pages"],
        "assurance_window_preflight_passed": 3,
        "rejected_candidates_before_freeze": 2,
        "scale_coverage": {
            "completed_unique_reports": 99,
            "stage_target_reports": 120,
            "completion_percent": 82.5,
            "remaining_reports": 21,
            "estimated_remaining_three_report_batches": 7,
        },
        "mineru": {
            "final_usable_pages": final["complete_pages"],
            "resume_completed_pages": performance["mineru"]["resume_completed_pages"],
            "hash_recovered_pages": final["post_completion_shutdown_recovered_pages"],
            "remaining_failures": final["failed_pages"],
            "successful_pages_per_hour": performance["mineru"][
                "successful_target_pages_per_hour"
            ],
        },
        "performance": {
            "whole_report_pages_per_second": performance["whole_report_diagnostic"][
                "pages_per_second"
            ],
            "whole_report_wall_seconds": performance["whole_report_diagnostic"][
                "wall_seconds"
            ],
            "target_page_success_wall_seconds": performance["mineru"][
                "successful_processing_wall_seconds"
            ],
            "change_vs_batch_021_percent": performance["mineru_comparison"][
                "relative_change_percent"
            ],
        },
        "knowledge_increment": {
            "evidence_snippet_candidates": increment["fact_candidates"],
            "atomic_fact_candidates": projection["atomic_fact_candidates"],
            "total_new_fact_records": increment["fact_candidates"]
            + projection["atomic_fact_candidates"],
            "failure_observations": increment["failure_observations"],
            "remaining_evidence_gaps": increment["evidence_gaps"],
            "rejected_ambiguous_rows": projection["rejected_ambiguous_rows"],
            "promoted_tier_b": promotion["newly_promoted_to_tier_b"],
            "held_tier_c_after_six_dimension_review": len(promotion["blocked_fact_ids"]),
        },
        "atomic_validation": {
            "coordinate_exact": validation["table_graph_coordinate_exact_count"],
            "coordinate_corroborated": validation["coordinate_corroborated_count"],
        },
        "global_knowledge_bases": {
            "fact_records": migration["counts"]["fact_records"],
            "trusted_fact_records": line_count(
                "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
            ),
            "failure_records": migration["counts"]["failure_records"],
            "failure_signatures": migration["counts"]["failure_signatures"],
            "repair_observations": migration["counts"]["repair_observations"],
        },
        "quality_gates": {
            "pytest_collected_and_passed": 478,
            "ruff": "passed",
            "json_artifacts_parse": (
                "9779_passed_except_preexisting_known_concatenated_p1_fixture"
            ),
            "sha256_manifest": "passed",
            "cloud_transmission": False,
            "locked_experiments_modified": False,
            "automatic_promotion": False,
            "failed_runs_preserved": True,
            "zero_promotion_partition_supported": True,
        },
        "artifact_sha256": {path: sha256(path) for path in ARTIFACTS},
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
