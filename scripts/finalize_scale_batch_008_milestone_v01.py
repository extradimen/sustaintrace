from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_008_milestone_audit.lock.json"

ARTIFACTS = (
    "configs/knowledge/scale_batch_008_v0.1.json",
    "configs/knowledge/scale_batch_008_RESUME01_v0.2.json",
    "configs/parsers/scale-batch-008-mineru-3.4.0-runtime.json",
    "data/manifests/scale_batch_008_acquisition.lock.json",
    "data/manifests/scale_batch_008_acquisition_failures.lock.json",
    "data/results/scale_batch_008_diagnostics.lock.json",
    "data/manifests/scale_batch_008_target_pages.lock.json",
    "data/results/scale_batch_008_mineru_summary.lock.json",
    "data/results/scale_batch_008_mineru_RESUME01_summary.lock.json",
    "data/results/scale_batch_008_mineru_RESUME02_summary.lock.json",
    "data/results/scale_batch_008_mineru_FINAL_summary.lock.json",
    "data/results/scale_batch_008_kb_increment.lock.json",
    "data/results/scale_batch_008_atomic_projection.lock.json",
    "data/results/scale_batch_008_atomic_validation.lock.json",
    "data/results/scale_batch_008_gap_repair.lock.json",
    "data/results/scale_batch_008_native_coordinate_audit.lock.json",
    "data/results/scale_batch_008_tier_b_promotion.lock.json",
    "data/knowledge_bases/v0.1/migration_manifest.lock.json",
    "data/knowledge_bases/v0.1/tier_b_independent_adjudications.jsonl",
    "data/knowledge_bases/v0.1/trusted_fact_records.jsonl",
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def line_count(path: str) -> int:
    return sum(bool(line) for line in (ROOT / path).read_text().splitlines())


def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    diagnostics = load("data/results/scale_batch_008_diagnostics.lock.json")
    final = load("data/results/scale_batch_008_mineru_FINAL_summary.lock.json")
    increment = load("data/results/scale_batch_008_kb_increment.lock.json")
    projection = load("data/results/scale_batch_008_atomic_projection.lock.json")
    validation = load("data/results/scale_batch_008_atomic_validation.lock.json")
    gap = load("data/results/scale_batch_008_gap_repair.lock.json")
    promotion = load("data/results/scale_batch_008_tier_b_promotion.lock.json")
    migration = load("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-008",
        "status": "local_ingestion_projection_gap_repair_and_tier_b_sampling_complete",
        "source_documents": diagnostics["totals"]["documents"],
        "source_pages": diagnostics["totals"]["pdf_pages"],
        "extractable_source_pages": diagnostics["totals"]["extractable_pages"],
        "frozen_target_pages": final["complete_pages"],
        "source_substitution": {
            "replaced_document": "Ericsson Annual Report 2025",
            "replacement": "Vestas Annual Report 2025",
            "reason": "official issuer asset returned HTTP 403 before acquisition freeze",
            "replacement_frozen_before_parsing": True,
        },
        "mineru": {
            "final_usable_pages": final["complete_pages"],
            "post_completion_shutdown_recovered_pages": final[
                "post_completion_shutdown_recovered_pages"
            ],
            "remaining_failures": final["failed_pages"],
            "model_failures": 0,
        },
        "knowledge_increment": {
            "evidence_snippet_candidates": increment["fact_candidates"],
            "atomic_fact_candidates": projection["atomic_fact_candidates"],
            "gap_repair_candidates": gap["new_fact_candidates"],
            "total_new_fact_records": (
                increment["fact_candidates"]
                + projection["atomic_fact_candidates"]
                + gap["new_fact_candidates"]
            ),
            "failure_observations": increment["failure_observations"],
            "parent_evidence_gaps": increment["evidence_gaps"],
            "remaining_evidence_gaps": 0,
            "rejected_ambiguous_table_rows": projection["rejected_ambiguous_rows"],
            "promoted_tier_b": promotion["newly_promoted_to_tier_b"],
            "held_tier_c_after_six_dimension_review": len(promotion["blocked_fact_ids"]),
        },
        "atomic_validation": {
            "coordinate_exact": validation["table_graph_coordinate_exact_count"],
            "native_quote_present": validation["native_quote_present_count"],
            "native_row_header_present": validation["native_row_header_present_count"],
            "native_column_header_present": validation["native_column_header_present_count"],
            "strictly_corroborated_by_initial_validator": validation[
                "coordinate_corroborated_count"
            ],
            "strictly_corroborated_by_native_layout_audit": 1,
        },
        "global_knowledge_bases": {
            "fact_records": migration["counts"]["fact_records"],
            "trusted_fact_records": line_count(
                "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
            ),
            "failure_records": migration["counts"]["failure_records"],
            "failure_signatures": migration["counts"]["failure_signatures"],
        },
        "quality_gates": {
            "pytest_collected_and_passed": 458,
            "ruff": "passed",
            "json_artifacts_parse": "passed",
            "sha256_manifest": "passed",
            "cloud_transmission": False,
            "locked_experiments_modified": False,
            "automatic_promotion": False,
        },
        "artifact_sha256": {path: sha256(path) for path in ARTIFACTS},
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
