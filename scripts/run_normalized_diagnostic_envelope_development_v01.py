#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.postvalidation_attachment import (
    GAP_DIMENSIONS,
    build_diagnostic_result_envelope,
    build_postvalidation_attachment,
    validate_postvalidation_attachment,
)

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "artifacts/heterogeneous_component_validation_v0.1/validation_summary.lock.json"
MANIFEST = ROOT / "data/manifests/heterogeneous_component_validation_RESUME01_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/normalized_diagnostic_envelope_development_v0.1"
CASES = {
    "HET-PERIOD-POS-NOVO-001",
    "HET-PERIOD-POS-SANOFI-001",
    "HET-TABLE-POS-BAYER-001",
}


def _jsonl(path: Path) -> dict[str, dict]:
    items = [json.loads(line) for line in path.read_text().splitlines() if line]
    key = "record_id" if path == FACTS else "gap_id"
    return {item[key]: item for item in items}


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_normalized_envelope_development")
    validation = json.loads(VALIDATION.read_text())
    manifest = json.loads(MANIFEST.read_text())
    records = {item["case_id"]: item for item in validation["records"]}
    cases = {item["case_id"]: item for item in manifest["cases"]}
    facts = _jsonl(FACTS)
    gaps = _jsonl(GAPS)
    OUTPUT.mkdir(parents=True)
    results = []
    for case_id in sorted(CASES):
        record = records[case_id]
        case = cases[case_id]
        raw_path = record["path"]
        raw = json.loads((ROOT / raw_path).read_text())
        envelope = build_diagnostic_result_envelope(
            payload=raw,
            diagnostic_path=raw_path,
            parent_fact_id=case["fact_record_id"],
            parent_gap_id=case["gap_id"],
            case_id=case_id,
            root=ROOT,
        )
        envelope_path = OUTPUT / f"{case_id.lower()}.envelope.json"
        envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
        fact = facts[case["fact_record_id"]]
        gap = gaps[case["gap_id"]]
        attachment = build_postvalidation_attachment(
            fact=fact,
            gap=gap,
            diagnostic_path=str(envelope_path.relative_to(ROOT)),
            satisfied_dimensions=sorted(GAP_DIMENSIONS[gap["gap_signature"]]),
            remaining_dimensions=[],
            root=ROOT,
        )
        reasons = validate_postvalidation_attachment(attachment, fact, gap, ROOT)
        attachment_path = OUTPUT / f"{case_id.lower()}.attachment.json"
        attachment_path.write_text(
            json.dumps(attachment, ensure_ascii=False, indent=2) + "\n"
        )
        results.append(
            {
                "case_id": case_id,
                "component": case["component"],
                "normalized_status": envelope["normalized_status"],
                "identity_binding": envelope["identity_binding"],
                "attachment_valid": not reasons,
                "attachment_validation_reasons": reasons,
                "envelope": {
                    "path": str(envelope_path.relative_to(ROOT)),
                    "sha256": sha256_file(envelope_path),
                },
                "attachment": {
                    "path": str(attachment_path.relative_to(ROOT)),
                    "sha256": sha256_file(attachment_path),
                },
            }
        )
    summary = {
        "schema_version": "0.1",
        "record_kind": "normalized_diagnostic_envelope_development_summary",
        "status": "development_complete",
        "source_validation": {
            "path": str(VALIDATION.relative_to(ROOT)),
            "sha256": sha256_file(VALIDATION),
            "modified": False,
            "reexecuted": False,
        },
        "results": results,
        "counts": {
            "cases": len(results),
            "normalized_passed": sum(
                item["normalized_status"] == "passed" for item in results
            ),
            "attachments_valid": sum(item["attachment_valid"] for item in results),
        },
        "calculation_without_registered_parent_gap_promoted": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
    }
    summary_path = OUTPUT / "development_summary.lock.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary["counts"]))


if __name__ == "__main__":
    main()
