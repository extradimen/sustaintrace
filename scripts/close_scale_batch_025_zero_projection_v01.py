from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
FAILURES = KB / "increments/scale_batch_025_failure_records.jsonl"
INCREMENT = ROOT / "data/results/scale_batch_025_kb_increment.lock.json"
PROJECTION = ROOT / "data/results/scale_batch_025_atomic_projection.lock.json"
AUDIT = ROOT / "data/results/scale_batch_025_native_coordinate_audit.lock.json"
PROMOTION = ROOT / "data/results/scale_batch_025_tier_b_promotion.lock.json"

SOURCES = {
    "KB-B025-EQUINOR-AR2025": {
        "path": ROOT / "data/raw/scale_batch_025/equinor-annual-report-2025.pdf",
        "sha256": "4266bb0b2f31bb9a8cc2ed11248cd579e0f98bb3c81fcffaf5c93a89e62e5d98",
        "pages": [305, 306, 307],
        "literals": [
            "consolidated sustainability statement of Equinor ASA",
            "31 December 2025",
            "nothing has come to our attention",
            "Tor Inge Skjellevik",
        ],
    },
    "KB-B025-AKERBP-AR2025": {
        "path": ROOT / "data/raw/scale_batch_025/aker-bp-annual-report-2025.pdf",
        "sha256": "c5afca29558be6e5daf6cf8e31b378fdd2542bd29b847f3ec96fce10172a1a15",
        "pages": [126, 127],
        "literals": [
            "consolidated sustainability statement of Aker BP ASA",
            "31 December 2025",
            "nothing has come to our attention",
            "Per Arvid Gimre",
        ],
    },
    "KB-B025-DNB-AR2025": {
        "path": ROOT / "data/raw/scale_batch_025/dnb-annual-report-2025.pdf",
        "sha256": "e793bbb20582975be0ee87825cafe7d05ad8e80f986f446d8cbfad7e2c84c125",
        "pages": [350, 351, 352, 353],
        "literals": [
            "consolidated sustainability statement of DNB Bank ASA",
            "31 December 2025",
            "nothing has come to our attention",
            "Kjetil Rimstad",
        ],
    },
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_text(path: Path, page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def main() -> None:
    if AUDIT.exists() or PROMOTION.exists():
        raise RuntimeError("refusing to overwrite Batch25 closure artifacts")
    projection = json.loads(PROJECTION.read_text())
    if projection["source_table_candidates"] != 2 or projection["atomic_fact_candidates"] != 0:
        raise ValueError("zero-projection inventory changed")
    records = [json.loads(line) for line in FAILURES.read_text().splitlines() if line]
    source_hash = sha(PROJECTION)
    identity = "KB-SCALE-BATCH-025|TABLE-FRAGMENT-WITHOUT-ATOMIC-NUMERIC-CELLS|" + source_hash
    record = {
        "schema_version": "0.1",
        "record_kind": "failure_observation",
        "record_id": "failure-" + hashlib.sha256(identity.encode()).hexdigest()[:24],
        "experiment_id": "KB-SCALE-BATCH-025",
        "task_id": "ATOMIC-PROJECTION-B025",
        "failure_owner": "document_pipeline",
        "failure_category": "parser_or_document_structure",
        "failure_signature": "TABLE_FRAGMENT_WITHOUT_ATOMIC_NUMERIC_CELLS",
        "observed_stage_states": {
            "stage": "deterministic_two_axis_projection",
            "status": "failed_closed",
        },
        "diagnostics": [
            {
                "source_table_candidates": 2,
                "atomic_fact_candidates": 0,
                "action": "retain_evidence_candidates_at_tier_c_without_semantic_repair",
            }
        ],
        "provenance": {
            "source_artifact": PROJECTION.relative_to(ROOT).as_posix(),
            "source_sha256": source_hash,
        },
    }
    if not any(item["record_id"] == record["record_id"] for item in records):
        records.append(record)
    schema = json.loads((ROOT / "schemas/knowledge/failure-record-v0.1.schema.json").read_text())
    for item in records:
        Draft202012Validator(schema).validate(item)
    FAILURES.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records)
    )
    increment = json.loads(INCREMENT.read_text())
    increment["failure_observations"] = len(records)
    increment["outputs"]["failures"]["sha256"] = sha(FAILURES)
    INCREMENT.write_text(json.dumps(increment, indent=2) + "\n")

    checks = {}
    page_hashes = {}
    for document_id, source in SOURCES.items():
        checks[f"{document_id}:source_sha256"] = sha(source["path"]) == source["sha256"]
        texts = [page_text(source["path"], page) for page in source["pages"]]
        normalized = " ".join("\n".join(texts).casefold().split())
        for index, literal in enumerate(source["literals"], 1):
            checks[f"{document_id}:assurance_literal_{index}"] = (
                " ".join(literal.casefold().split()) in normalized
            )
        for page, text in zip(source["pages"], texts, strict=True):
            page_hashes[f"{document_id}:p{page}"] = hashlib.sha256(text.encode()).hexdigest()
    if not all(checks.values()):
        raise ValueError([key for key, passed in checks.items() if not passed])
    audit = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-025-NATIVE-COORDINATE-AUDIT",
        "status": "assurance_boundaries_passed_no_atomic_cells_eligible",
        "promotable_facts": 0,
        "checks": checks,
        "assurance_page_text_sha256": page_hashes,
        "projection_failure_signature": record["failure_signature"],
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    trusted = KB / "trusted_fact_records.jsonl"
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_025_six_dimension_tier_b_review_complete_fail_closed",
        "reviewed": 0,
        "newly_promoted_to_tier_b": 0,
        "promotable_fact_ids": [],
        "blocked_fact_ids": [],
        "blocked_by_reason": {"no_atomic_numeric_cells_survived_deterministic_projection": []},
        "total_trusted_tier_b": sum(bool(line) for line in trusted.read_text().splitlines()),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha(
                KB / "increments/scale_batch_025_atomic_fact_records.jsonl"
            ),
            "atomic_validations_sha256": sha(
                KB / "increments/scale_batch_025_atomic_validations.jsonl"
            ),
            "native_coordinate_audit_sha256": sha(AUDIT),
        },
        "outputs": {"trusted_facts_sha256": sha(trusted)},
        "native_audit": audit,
        "next_gate": "scale_batch_025_global_kb_rebuild_and_closure",
    }
    PROMOTION.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "failure_observations": len(records),
                "promoted_tier_b": 0,
                "assurance_checks": len(checks),
            }
        )
    )


if __name__ == "__main__":
    main()
