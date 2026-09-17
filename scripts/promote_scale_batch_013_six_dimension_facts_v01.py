from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_013_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_013_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_013_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_013_native_coordinate_audit.lock.json"
FAILURES = KB / "increments/scale_batch_013_semantic_failure_records.jsonl"
SOURCE = ROOT / "data/raw/scale_batch_013/wartsila-annual-report-2025.pdf"
SOURCE_SHA256 = "55737cdd163cb2c7077ef46afd42184debfd9a3116cb02b1f63ba5e53f20c3cb"


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
    if len(candidates) != 8 or set(candidates) != set(validations):
        raise ValueError("fail-closed: batch-thirteen atomic inventory changed")

    data_page = pdf_page(129)
    frozen_assurance_page = pdf_page(226)
    checks = {
        "source_sha256_matches": sha256_file(SOURCE) == SOURCE_SHA256,
        "employee_table_present": "Characteristics of undertaking's employees" in data_page,
        "year_headers_present": "2025" in data_page and "2024" in data_page,
        "all_projected_values_present": all(
            item["evidence"][0]["quote"] in data_page for item in candidates.values()
        ),
        "all_frozen_coordinates_corroborated": all(
            item["checks"]["table_graph_coordinate_exact"]
            and item["coordinate_corroborated"]
            for item in validations.values()
        ),
        "frozen_assurance_page_has_limited_assurance_language": (
            "limited assurance engagement" in frozen_assurance_page
        ),
        "frozen_assurance_page_has_issuer_identity": (
            "Wärtsilä Corporation" in frozen_assurance_page
        ),
        "frozen_assurance_page_has_reporting_period": (
            "1.1–31.12.2025" in frozen_assurance_page
        ),
        "frozen_assurance_page_has_opinion": "Opinion" in frozen_assurance_page,
    }
    required_coordinate_checks = (
        "source_sha256_matches",
        "employee_table_present",
        "year_headers_present",
        "all_projected_values_present",
        "all_frozen_coordinates_corroborated",
        "frozen_assurance_page_has_limited_assurance_language",
    )
    if not all(checks[key] for key in required_coordinate_checks):
        raise ValueError(f"native coordinate audit failed: {checks}")
    assurance_scope_complete = all(
        checks[key]
        for key in (
            "frozen_assurance_page_has_issuer_identity",
            "frozen_assurance_page_has_reporting_period",
            "frozen_assurance_page_has_opinion",
        )
    )
    if assurance_scope_complete:
        raise ValueError("fail-closed: expected frozen assurance-window gap is absent")

    blocked_reason = "frozen_assurance_window_omits_identity_period_and_opinion"
    blocked = {fact_id: blocked_reason for fact_id in candidates}
    diagnostic = {
        "document_id": "KB-B013-WARTSILA-AR2025",
        "data_pdf_page": 129,
        "frozen_assurance_pdf_page": 226,
        "affected_fact_ids": sorted(candidates),
        "coordinate_evidence_complete": True,
        "assurance_scope_complete": False,
        "missing_frozen_assurance_fields": ["issuer_identity", "reporting_period", "opinion"],
        "decision": "retain_candidates_at_tier_c_do_not_expand_frozen_window_post_hoc",
    }
    semantic_failures = [
        {
            "schema_version": "0.1",
            "record_kind": "failure_observation",
            "record_id": stable_id(
                "failure", ["KB-SCALE-BATCH-013", "TARGET_ASSURANCE_WINDOW_INCOMPLETE", diagnostic]
            ),
            "experiment_id": "KB-SCALE-BATCH-013",
            "task_id": "KB-B013-WARTSILA-AR2025-P0226-ASSURANCE-WINDOW-AUDIT",
            "failure_owner": "framework",
            "failure_category": "retrieval_or_evidence_selection",
            "failure_signature": "TARGET_ASSURANCE_WINDOW_INCOMPLETE",
            "observed_stage_states": {
                "stage": "six_dimension_promotion_review",
                "status": "assurance_scope_failed_closed",
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
        "batch_id": "KB-SCALE-BATCH-013-NATIVE-COORDINATE-AUDIT",
        "status": "coordinates_passed_assurance_window_failed_closed",
        "checks": checks,
        "native_data_page_sha256": hashlib.sha256(data_page.encode()).hexdigest(),
        "native_frozen_assurance_page_sha256": hashlib.sha256(
            frozen_assurance_page.encode()
        ).hexdigest(),
        "blocked_by_reason": {blocked_reason: sorted(candidates)},
        "policy": {
            "cloud_transmission": False,
            "automatic_promotion": False,
            "post_hoc_window_expansion": False,
        },
    }
    NATIVE_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_013_six_dimension_review_complete_zero_promotions",
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
        "next_gate": "scale_batch_013_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
