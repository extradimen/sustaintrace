from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_012_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_012_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_012_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_012_native_coordinate_audit.lock.json"
FAILURES = KB / "increments/scale_batch_012_semantic_failure_records.jsonl"
SOURCE = ROOT / "data/raw/scale_batch_012/stora-enso-annual-report-2025.pdf"
SOURCE_SHA256 = "00377e8fb8a6b2fc866d38a7f68e6cccd8099c9fe5f79be4da96d7f46bb4bbf0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )


def pdf_page(page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(SOURCE), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def main() -> None:
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    validations = {item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)}
    if len(candidates) != 4 or set(candidates) != set(validations):
        raise ValueError("fail-closed: batch-twelve atomic inventory changed")

    page = pdf_page(105)
    checks = {
        "source_sha256_matches": sha256_file(SOURCE) == SOURCE_SHA256,
        "table_header_present": "Target, m3/tonne" in page.replace("³", "3"),
        "process_discharge_fragments_present": all(
            token in page
            for token in ("Decrease in process", "saleable tonne of", "by 17% by 2030")
        ),
        "withdrawal_fragments_present": all(
            token in page
            for token in ("Continuous target on", "for total water", "saleable tonne")
        ),
        "all_values_present": all(value in page.split() for value in ("32", "34", "56", "60")),
        "all_frozen_graph_coordinates_exact": all(
            item["checks"]["table_graph_coordinate_exact"] for item in validations.values()
        ),
        "all_native_row_headers_exact": all(
            item["checks"]["native_row_header_present"] for item in validations.values()
        ),
        "signed_independent_assurance_cell_scope_verified": False,
    }
    required = (
        "source_sha256_matches",
        "table_header_present",
        "process_discharge_fragments_present",
        "withdrawal_fragments_present",
        "all_values_present",
        "all_frozen_graph_coordinates_exact",
    )
    if not all(checks[key] for key in required):
        raise ValueError(f"native coordinate audit failed: {checks}")

    blocked = {
        fact_id: "native_pdf_line_wrapping_prevents_exact_row_header_corroboration"
        for fact_id in candidates
    }
    diagnostic = {
        "document_id": "KB-B012-STORA-ENSO-AR2025",
        "pdf_page": 105,
        "affected_fact_ids": sorted(candidates),
        "values": sorted({item["value"] for item in candidates.values()}),
        "table_graph_coordinates_exact": True,
        "native_row_header_exact_match": False,
        "cause": "native PDF layout splits each semantic row label across multiple physical lines",
        "decision": "retain_candidates_at_tier_c_and_block_promotion",
    }
    semantic_failures = [
        {
            "schema_version": "0.1",
            "record_kind": "failure_observation",
            "record_id": stable_id(
                "failure",
                ["KB-SCALE-BATCH-012", "NATIVE_ROW_HEADER_LINE_WRAP_MISMATCH", diagnostic],
            ),
            "experiment_id": "KB-SCALE-BATCH-012",
            "task_id": "KB-B012-STORA-ENSO-AR2025-P0105-ATOMIC-PROJECTION-AUDIT",
            "failure_owner": "framework",
            "failure_category": "parser_or_document_structure",
            "failure_signature": "NATIVE_ROW_HEADER_LINE_WRAP_MISMATCH",
            "observed_stage_states": {
                "stage": "deterministic_atomic_projection_validation",
                "status": "native_row_header_exact_match_failed_closed",
            },
            "diagnostics": [diagnostic],
            "provenance": {
                "source_artifact": INCREMENT.relative_to(ROOT).as_posix(),
                "source_sha256": sha256_file(INCREMENT),
            },
        }
    ]
    validate_records(
        semantic_failures,
        json.loads((ROOT / "schemas/knowledge/failure-record-v0.1.schema.json").read_text()),
    )
    dump_jsonl(FAILURES, semantic_failures)

    audit = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-012-NATIVE-COORDINATE-AUDIT",
        "status": "coordinates_checked_promotion_failed_closed",
        "checks": checks,
        "native_page_105_sha256": hashlib.sha256(page.encode()).hexdigest(),
        "blocked_by_reason": {
            "native_pdf_line_wrapping_prevents_exact_row_header_corroboration": sorted(candidates)
        },
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_012_six_dimension_review_complete_zero_promotions",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": 0,
        "promotable_fact_ids": [],
        "blocked_fact_ids": sorted(blocked),
        "blocked_by_reason": audit["blocked_by_reason"],
        "new_failure_observations": len(semantic_failures),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha256_file(INCREMENT),
            "atomic_validations_sha256": sha256_file(VALIDATIONS),
            "native_coordinate_audit_sha256": sha256_file(NATIVE_AUDIT),
        },
        "outputs": {"semantic_failures_sha256": sha256_file(FAILURES)},
        "next_gate": "scale_batch_012_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
