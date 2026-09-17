from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_011_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_011_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_011_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_011_native_coordinate_audit.lock.json"
FAILURES = KB / "increments/scale_batch_011_semantic_failure_records.jsonl"
SOURCE = ROOT / "data/raw/scale_batch_011/eni-annual-report-2025-sustainability.pdf"
SOURCE_SHA256 = "999dd84dcfbd0baad741187e0006b22e1d86e6ddf0058e20f2cef7eaede1128c"


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
    if len(candidates) != 3 or set(candidates) != set(validations):
        raise ValueError("fail-closed: batch-eleven atomic inventory changed")

    page = pdf_page(78)
    assurance = pdf_page(8)
    checks = {
        "source_sha256_matches": sha256_file(SOURCE) == SOURCE_SHA256,
        "workforce_table_header_present": ("WORKFORCE OCCUPATIONAL SAFETY METRICS" in page),
        "trir_row_present": "0.55" in page and "0.70(b)" in page,
        "near_miss_row_present": "Near Miss(a)" in page,
        "near_miss_values_present": "634" in page and "563" in page,
        "assurance_claim_present": "subject to a limited assurance" in assurance,
        "signed_independent_assurance_report_present": False,
        "all_frozen_coordinates_corroborated": all(
            item["checks"]["table_graph_coordinate_exact"]
            and item["coordinate_corroborated"]
            for item in validations.values()
        ),
    }
    if not all(
        value
        for key, value in checks.items()
        if key != "signed_independent_assurance_report_present"
    ):
        raise ValueError(f"native coordinate audit failed: {checks}")

    blocked: dict[str, str] = {}
    semantic_failures = []
    for fact_id, fact in candidates.items():
        evidence = fact["evidence"][0]
        if evidence["quote"] in {"634", "563"}:
            blocked[fact_id] = "row_label_dropped_near_miss_misbound_as_unnamed_metric"
        else:
            blocked[fact_id] = "signed_independent_assurance_scope_not_in_frozen_evidence"

    misbound = sorted(
        fact_id
        for fact_id, reason in blocked.items()
        if reason == "row_label_dropped_near_miss_misbound_as_unnamed_metric"
    )
    diagnostic = {
        "document_id": "KB-B011-ENI-SS2025",
        "pdf_page": 78,
        "affected_fact_ids": misbound,
        "native_row_header": "Near Miss(a)",
        "projected_row_header": "(number)",
        "values": {"2025": "634", "2024": "563"},
        "decision": "retain_source_candidates_at_tier_c_and_block_promotion",
    }
    semantic_failures.append(
        {
            "schema_version": "0.1",
            "record_kind": "failure_observation",
            "record_id": stable_id(
                "failure", ["KB-SCALE-BATCH-011", "PARSER_TABLE_STRUCTURE", diagnostic]
            ),
            "experiment_id": "KB-SCALE-BATCH-011",
            "task_id": "KB-B011-ENI-SS2025-P0078-ATOMIC-PROJECTION-AUDIT",
            "failure_owner": "framework",
            "failure_category": "parser_or_document_structure",
            "failure_signature": "PARSER_TABLE_STRUCTURE",
            "observed_stage_states": {
                "stage": "deterministic_atomic_projection",
                "status": "semantic_row_binding_failed_closed",
            },
            "diagnostics": [diagnostic],
            "provenance": {
                "source_artifact": INCREMENT.relative_to(ROOT).as_posix(),
                "source_sha256": sha256_file(INCREMENT),
            },
        }
    )
    validate_records(
        semantic_failures,
        json.loads((ROOT / "schemas/knowledge/failure-record-v0.1.schema.json").read_text()),
    )
    dump_jsonl(FAILURES, semantic_failures)

    audit = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-011-NATIVE-COORDINATE-AUDIT",
        "status": "coordinates_checked_promotion_failed_closed",
        "checks": checks,
        "native_page_78_sha256": hashlib.sha256(page.encode()).hexdigest(),
        "native_assurance_page_8_sha256": hashlib.sha256(assurance.encode()).hexdigest(),
        "blocked_by_reason": {
            reason: sorted(fact_id for fact_id, value in blocked.items() if value == reason)
            for reason in sorted(set(blocked.values()))
        },
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_011_six_dimension_review_complete_zero_promotions",
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
        "next_gate": "scale_batch_011_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
