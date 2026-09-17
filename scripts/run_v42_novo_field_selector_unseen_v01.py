#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id
from esg_reliable_discovery.postvalidation_attachment import (
    build_diagnostic_result_envelope,
    build_postvalidation_attachment,
    validate_postvalidation_attachment,
)
from esg_reliable_discovery.promotion_gate import (
    evaluate_promotion_dry_run_with_attachments,
)
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/v42_novo_field_selector_unseen_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/v42_novo_field_selector_unseen_v0.1"


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_v42_novo_unseen")
    manifest = json.loads(MANIFEST.read_text())
    if sha256_file(FACTS) != manifest["parent"]["fact_store_sha256"]:
        raise ValueError("fact_store_hash_mismatch")
    if sha256_file(GAPS) != manifest["parent"]["gap_store_sha256"]:
        raise ValueError("gap_store_hash_mismatch")
    facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    gaps = _jsonl(GAPS)
    fact = facts[manifest["parent"]["fact_record_id"]]
    gap = next(item for item in gaps if item["gap_id"] == manifest["parent"]["gap_id"])
    if _canonical_sha256(fact["evidence"]) != manifest["parent"][
        "fact_evidence_canonical_sha256"
    ]:
        raise ValueError("fact_evidence_hash_mismatch")
    if sha256_file(ROOT / manifest["source"]["path"]) != manifest["source"]["sha256"]:
        raise ValueError("source_hash_mismatch")

    fixture = {
        "fixture_id": stable_id("v42-novo-field-selector-unseen", manifest),
        "gap_signature": gap["gap_signature"],
        "gap_id": gap["gap_id"],
        "fact_record_id": fact["record_id"],
        "native_source": manifest["source"],
        "evidence_pages": [manifest["selector"]["pdf_page"]],
        "source_literals": [item["quote"] for item in fact["evidence"]],
        "diagnostic_contract": {"required_fields": manifest["required_fields"]},
        "adapter_inputs": {"evidence_selector": manifest["selector"]},
        "rollback": {"action": "discard unseen derived artifacts"},
    }
    diagnostic = run_read_only_diagnostic(fixture, fact, ROOT)
    observed = diagnostic["diagnostic"]
    diagnostic_contract_passed = (
        diagnostic["status"] == manifest["expected"]["diagnostic_status"]
        and observed["collection_cardinality"]
        == manifest["expected"]["fact_evidence_count"]
        and observed["selected_collection_cardinality"]
        == manifest["expected"]["selected_collection_cardinality"]
        and observed["evidence_coordinates"][0]["match_count"]
        == manifest["expected"]["native_match_count"]
    )

    OUTPUT.mkdir(parents=True, exist_ok=False)
    parent_payload = {
        "schema_version": "0.1",
        "record_kind": "v42_unseen_diagnostic_case",
        "contract_passed": diagnostic_contract_passed,
        "execution_error": None,
        "observed": diagnostic,
        "attempts": 1,
    }
    parent_path = OUTPUT / "diagnostic_parent.lock.json"
    parent_path.write_text(json.dumps(parent_payload, ensure_ascii=False, indent=2) + "\n")
    envelope = build_diagnostic_result_envelope(
        payload=parent_payload,
        diagnostic_path=str(parent_path.relative_to(ROOT)),
        parent_fact_id=fact["record_id"],
        parent_gap_id=gap["gap_id"],
        case_id=manifest["experiment_id"],
        root=ROOT,
    )
    envelope_path = OUTPUT / "diagnostic_envelope.lock.json"
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
    attachment = build_postvalidation_attachment(
        fact=fact,
        gap=gap,
        diagnostic_path=str(envelope_path.relative_to(ROOT)),
        satisfied_dimensions=["field_or_cell_binding"],
        remaining_dimensions=[],
        root=ROOT,
    )
    attachment_path = OUTPUT / "qualification_attachment.lock.json"
    attachment_path.write_text(json.dumps(attachment, ensure_ascii=False, indent=2) + "\n")
    attachment_reasons = validate_postvalidation_attachment(attachment, fact, gap, ROOT)
    fact_gaps = [item for item in gaps if item["fact_record_id"] == fact["record_id"]]
    gate = evaluate_promotion_dry_run_with_attachments(
        fact, fact_gaps, [attachment], ROOT
    )
    gate_path = OUTPUT / "promotion_gate.lock.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n")

    contract_passed = (
        diagnostic_contract_passed
        and envelope["normalized_status"] == "passed"
        and not attachment_reasons
        and manifest["expected"]["attachment_valid"]
        and gate["promotion_performed"] is manifest["expected"]["promotion_performed"]
    )
    result = {
        "schema_version": "0.1",
        "experiment_id": manifest["experiment_id"],
        "status": "completed",
        "attempt_count": 1,
        "contract_passed": contract_passed,
        "diagnostic_status": diagnostic["status"],
        "envelope_status": envelope["normalized_status"],
        "attachment_valid": not attachment_reasons,
        "attachment_validation_reasons": attachment_reasons,
        "gate_decision": gate["decision"],
        "gate_blocking_reasons": gate["blocking_reasons"],
        "artifacts": [
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
            for path in (parent_path, envelope_path, attachment_path, gate_path)
        ],
        "historical_result_modified": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
        "cloud_transmission_performed": False,
    }
    result_path = OUTPUT / "result.lock.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"contract_passed": contract_passed, "gate": gate["decision"]}))


if __name__ == "__main__":
    main()
