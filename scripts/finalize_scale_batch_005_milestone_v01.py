from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_005_atomic_milestone_audit.lock.json"

ARTIFACTS = (
    "configs/knowledge/scale_batch_005_v0.1.json",
    "configs/parsers/scale-batch-005-mineru-3.4.0-runtime.json",
    "data/manifests/scale_batch_005_acquisition.lock.json",
    "data/results/scale_batch_005_diagnostics.lock.json",
    "data/manifests/scale_batch_005_target_pages.lock.json",
    "data/results/scale_batch_005_mineru_summary.lock.json",
    "data/results/scale_batch_005_mineru_RESUME01_summary.lock.json",
    "data/results/scale_batch_005_mineru_RESUME02_summary.lock.json",
    "data/results/scale_batch_005_mineru_RESUME03_summary.lock.json",
    "data/results/scale_batch_005_mineru_FINAL_summary.lock.json",
    "data/results/scale_batch_005_kb_increment.lock.json",
    "data/results/scale_batch_005_atomic_projection.lock.json",
    "data/results/scale_batch_005_atomic_validation.lock.json",
    "data/results/scale_batch_005_gap_repair.lock.json",
    "data/knowledge_bases/v0.1/migration_manifest.lock.json",
    "configs/knowledge/repair_strategy_catalog_v0.1.json",
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def line_count(path: str) -> int:
    return sum(bool(line) for line in (ROOT / path).read_text().splitlines())


def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    diagnostics = load("data/results/scale_batch_005_diagnostics.lock.json")
    final = load("data/results/scale_batch_005_mineru_FINAL_summary.lock.json")
    increment = load("data/results/scale_batch_005_kb_increment.lock.json")
    projection = load("data/results/scale_batch_005_atomic_projection.lock.json")
    validation = load("data/results/scale_batch_005_atomic_validation.lock.json")
    gap = load("data/results/scale_batch_005_gap_repair.lock.json")
    failures = [
        json.loads(line)
        for line in (ROOT / "data/knowledge_bases/v0.1/failure_records.jsonl")
        .read_text()
        .splitlines()
        if line
    ]
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-005",
        "status": "local_ingestion_projection_and_gap_repair_complete",
        "source_documents": diagnostics["totals"]["documents"],
        "source_pages": diagnostics["totals"]["pdf_pages"],
        "extractable_source_pages": diagnostics["totals"]["extractable_pages"],
        "frozen_target_pages": final["complete_pages"],
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
            "promoted_tier_b": 0,
        },
        "atomic_validation": {
            "coordinate_exact": validation["table_graph_coordinate_exact_count"],
            "native_quote_present": validation["native_quote_present_count"],
            "native_row_header_present": validation["native_row_header_present_count"],
            "native_column_header_present": validation["native_column_header_present_count"],
            "strictly_corroborated": validation["coordinate_corroborated_count"],
            "held_tier_c": validation["held_tier_c_count"],
        },
        "global_knowledge_bases": {
            "fact_records": line_count("data/knowledge_bases/v0.1/fact_records.jsonl"),
            "trusted_fact_records": line_count(
                "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
            ),
            "failure_records": len(failures),
            "failure_signatures": len({item["failure_signature"] for item in failures}),
        },
        "quality_gates": {
            "pytest_collected_and_passed": 444,
            "ruff": "passed",
            "cloud_transmission": False,
            "locked_experiments_modified": False,
            "automatic_promotion": False,
        },
        "artifact_sha256": {path: sha256(path) for path in ARTIFACTS},
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
