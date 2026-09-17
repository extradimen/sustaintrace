from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .knowledge_base import sha256_file, stable_id

GAP_DIMENSIONS = {
    "FIELD_EVIDENCE_BINDING_INCOMPLETE": {"field_or_cell_binding"},
    "TABLE_CELL_BINDING_INCOMPLETE": {"field_or_cell_binding"},
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": {"independent_corroboration"},
    "PERIOD_ATTACHMENT_INCOMPLETE": {"period_binding"},
    "UNIT_ATTACHMENT_INCOMPLETE": {"unit_binding"},
    "CALCULATION_LINEAGE_INCOMPLETE": {"calculation_lineage"},
}


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_diagnostic_result_envelope(
    *,
    payload: dict[str, Any],
    diagnostic_path: str,
    parent_fact_id: str,
    parent_gap_id: str,
    case_id: str,
    root: Path,
) -> dict[str, Any]:
    """Normalize component-specific results without changing their raw payload."""
    path = root / diagnostic_path
    if not path.is_file():
        raise ValueError("diagnostic_artifact_missing")
    reasons: list[str] = []
    actual_payload = json.loads(path.read_text())
    if actual_payload != payload:
        reasons.append("parent_payload_mismatch")

    result_payload = payload
    result_path = "top_level"
    if "raw_result" in payload:
        raw_result = payload["raw_result"]
        if not isinstance(raw_result, dict):
            reasons.append("raw_result_not_object")
            result_payload = {}
        elif "raw_result" in raw_result:
            reasons.append("nested_raw_result_not_allowed")
            result_payload = {}
        else:
            result_payload = raw_result
            result_path = "raw_result"
    observed = result_payload.get("observed", result_payload)
    if payload.get("contract_passed") is not True:
        reasons.append("parent_contract_not_passed")
    if payload.get("execution_error"):
        reasons.append("parent_execution_error")
    if result_payload.get("execution_error"):
        reasons.append("component_execution_error")
    observed_fact = observed.get("fact_record_id")
    observed_gap = observed.get("gap_id")
    if observed_fact is not None and observed_fact != parent_fact_id:
        reasons.append("parent_fact_identity_conflict")
    if observed_gap is not None and observed_gap != parent_gap_id:
        reasons.append("parent_gap_identity_conflict")
    blocking = observed.get("blocking_reasons") or []
    if blocking:
        reasons.append("component_reported_blocking_reasons")
    passed_shape = observed.get("status") == "passed"
    eligible_shape = observed.get("eligibility") == "eligible"
    if not (passed_shape or eligible_shape):
        reasons.append("component_result_not_positive")

    body = {
        "schema_version": "0.1",
        "record_kind": "normalized_read_only_diagnostic_envelope",
        "case_id": case_id,
        "parent_fact_id": parent_fact_id,
        "parent_gap_id": parent_gap_id,
        "normalized_status": "passed" if not reasons else "blocked",
        "blocking_reasons": sorted(set(reasons)),
        "identity_binding": {
            "fact_id_source": "diagnostic" if observed_fact is not None else "frozen_manifest",
            "gap_id_source": "diagnostic" if observed_gap is not None else "frozen_manifest",
            "component_fixture_id": observed.get("fixture_id"),
            "component_result_path": result_path,
        },
        "parent_artifact": {
            "path": diagnostic_path,
            "sha256": sha256_file(path),
        },
        "raw_payload": payload,
        "parent_artifact_modified": False,
    }
    signed = dict(body)
    signed["integrity_signature"] = {
        "algorithm": "sha256-canonical-json",
        "digest": _canonical_sha256(body),
    }
    return signed


def build_postvalidation_attachment(
    *,
    fact: dict[str, Any],
    gap: dict[str, Any],
    diagnostic_path: str,
    satisfied_dimensions: list[str],
    remaining_dimensions: list[str],
    root: Path,
) -> dict[str, Any]:
    path = root / diagnostic_path
    if not path.is_file():
        raise ValueError("diagnostic_artifact_missing")
    source = (fact.get("subject", {}).get("document_metadata") or [{}])[0]
    body = {
        "schema_version": "0.1",
        "record_kind": "postvalidation_qualification_attachment",
        "parent_fact_id": fact["record_id"],
        "parent_gap_id": gap["gap_id"],
        "parent_gap_signature": gap["gap_signature"],
        "diagnostic": {
            "path": diagnostic_path,
            "sha256": sha256_file(path),
        },
        "source": {
            "path": source.get("local_path"),
            "sha256": source.get("sha256"),
        },
        "satisfied_dimensions": sorted(set(satisfied_dimensions)),
        "remaining_dimensions": sorted(set(remaining_dimensions)),
        "generation_rule": (
            "consume only a passed, hash-matched diagnostic for the same immutable "
            "parent fact and gap"
        ),
        "parent_records_modified": False,
        "gap_closed": False,
        "promotion_authorized": False,
        "rollback_plan": {
            "action": "discard attachment",
            "parent_fact_unchanged": True,
            "parent_gap_unchanged": True,
        },
    }
    body["attachment_id"] = stable_id("postvalidation-attachment", body)
    signed = dict(body)
    signed["integrity_signature"] = {
        "algorithm": "sha256-canonical-json",
        "digest": _canonical_sha256(body),
    }
    return signed


def validate_postvalidation_attachment(
    attachment: dict[str, Any],
    fact: dict[str, Any],
    gap: dict[str, Any],
    root: Path,
) -> list[str]:
    reasons = []
    signature = attachment.get("integrity_signature") or {}
    unsigned = {key: value for key, value in attachment.items() if key != "integrity_signature"}
    if signature.get("algorithm") != "sha256-canonical-json" or signature.get(
        "digest"
    ) != _canonical_sha256(unsigned):
        reasons.append("ATTACHMENT_INTEGRITY_SIGNATURE_INVALID")
    if attachment.get("parent_fact_id") != fact.get("record_id"):
        reasons.append("ATTACHMENT_FACT_MISMATCH")
    if attachment.get("parent_gap_id") != gap.get("gap_id"):
        reasons.append("ATTACHMENT_GAP_MISMATCH")
    if attachment.get("parent_gap_signature") != gap.get("gap_signature"):
        reasons.append("ATTACHMENT_GAP_SIGNATURE_MISMATCH")

    allowed = GAP_DIMENSIONS.get(gap.get("gap_signature"), set())
    claimed = set(attachment.get("satisfied_dimensions") or [])
    if not claimed or not claimed <= allowed:
        reasons.append("ATTACHMENT_DIMENSION_CLAIM_UNAUTHORIZED")

    diagnostic = attachment.get("diagnostic") or {}
    diagnostic_path = diagnostic.get("path")
    if not diagnostic_path or not (root / diagnostic_path).is_file():
        reasons.append("ATTACHMENT_DIAGNOSTIC_MISSING")
    elif sha256_file(root / diagnostic_path) != diagnostic.get("sha256"):
        reasons.append("ATTACHMENT_DIAGNOSTIC_HASH_MISMATCH")
    else:
        payload = json.loads((root / diagnostic_path).read_text())
        if payload.get("record_kind") == "normalized_read_only_diagnostic_envelope":
            envelope_signature = payload.get("integrity_signature") or {}
            envelope_unsigned = {
                key: value for key, value in payload.items() if key != "integrity_signature"
            }
            envelope_algorithm = envelope_signature.get("algorithm")
            envelope_digest = envelope_signature.get("digest")
            if (
                envelope_algorithm != "sha256-canonical-json"
                or envelope_digest != _canonical_sha256(envelope_unsigned)
            ):
                reasons.append("ATTACHMENT_DIAGNOSTIC_ENVELOPE_SIGNATURE_INVALID")
            if payload.get("normalized_status") != "passed":
                reasons.append("ATTACHMENT_DIAGNOSTIC_NOT_PASSED")
            if payload.get("parent_fact_id") != fact.get("record_id"):
                reasons.append("ATTACHMENT_DIAGNOSTIC_FACT_MISMATCH")
            if payload.get("parent_gap_id") != gap.get("gap_id"):
                reasons.append("ATTACHMENT_DIAGNOSTIC_GAP_MISMATCH")
            parent = payload.get("parent_artifact") or {}
            parent_path = parent.get("path")
            if not parent_path or not (root / parent_path).is_file():
                reasons.append("ATTACHMENT_DIAGNOSTIC_PARENT_MISSING")
            elif sha256_file(root / parent_path) != parent.get("sha256"):
                reasons.append("ATTACHMENT_DIAGNOSTIC_PARENT_HASH_MISMATCH")
        else:
            observed = payload.get("observed", payload)
            if payload.get("contract_passed") is not True or observed.get("status") != "passed":
                reasons.append("ATTACHMENT_DIAGNOSTIC_NOT_PASSED")
            if observed.get("fact_record_id") != fact.get("record_id"):
                reasons.append("ATTACHMENT_DIAGNOSTIC_FACT_MISMATCH")
            if observed.get("gap_id") != gap.get("gap_id"):
                reasons.append("ATTACHMENT_DIAGNOSTIC_GAP_MISMATCH")

    source = attachment.get("source") or {}
    source_path = source.get("path")
    expected_source = (fact.get("subject", {}).get("document_metadata") or [{}])[0]
    if (
        source_path != expected_source.get("local_path")
        or source.get("sha256") != expected_source.get("sha256")
    ):
        reasons.append("ATTACHMENT_SOURCE_REFERENCE_MISMATCH")
    elif not source_path or not (root / source_path).is_file():
        reasons.append("ATTACHMENT_SOURCE_MISSING")
    elif sha256_file(root / source_path) != source.get("sha256"):
        reasons.append("ATTACHMENT_SOURCE_HASH_MISMATCH")

    if attachment.get("parent_records_modified") is not False:
        reasons.append("ATTACHMENT_PARENT_MUTATION_CLAIMED")
    if attachment.get("gap_closed") is not False:
        reasons.append("ATTACHMENT_UNAUTHORIZED_GAP_CLOSURE")
    if attachment.get("promotion_authorized") is not False:
        reasons.append("ATTACHMENT_UNAUTHORIZED_PROMOTION")
    return sorted(set(reasons))
