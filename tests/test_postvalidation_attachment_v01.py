import copy
import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.postvalidation_attachment import (
    build_diagnostic_result_envelope,
    build_postvalidation_attachment,
    validate_postvalidation_attachment,
)
from esg_reliable_discovery.promotion_gate import (
    evaluate_promotion_dry_run_with_attachments,
)


def _inputs(tmp_path: Path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    fact = {
        "record_id": "fact-a",
        "trust_tier": "C",
        "value": "narrative",
        "predicate": {"canonical_key": "policy"},
        "subject": {
            "document_metadata": [
                {
                    "local_path": "source.pdf",
                    "sha256": hashlib.sha256(b"source").hexdigest(),
                }
            ]
        },
        "evidence": [
            {
                "quote": "narrative",
                "pdf_page": 1,
                "role": "signed independent assurance",
            }
        ],
        "qualifiers": {
            "reference_period": 2025,
            "scope_boundary": "group",
            "normalized_unit": None,
            "calculation_expression": None,
        },
        "provenance": {"simulated": False},
    }
    gap = {
        "gap_id": "gap-a",
        "fact_record_id": "fact-a",
        "gap_signature": "FIELD_EVIDENCE_BINDING_INCOMPLETE",
    }
    diagnostic = {
        "contract_passed": True,
        "observed": {"status": "passed", "fact_record_id": "fact-a", "gap_id": "gap-a"},
    }
    (tmp_path / "diagnostic.json").write_text(json.dumps(diagnostic))
    attachment = build_postvalidation_attachment(
        fact=fact,
        gap=gap,
        diagnostic_path="diagnostic.json",
        satisfied_dimensions=["field_or_cell_binding"],
        remaining_dimensions=[],
        root=tmp_path,
    )
    return fact, gap, attachment


def test_valid_attachment_is_consumed_without_mutating_parent(tmp_path):
    fact, gap, attachment = _inputs(tmp_path)
    original = copy.deepcopy(fact)
    result = evaluate_promotion_dry_run_with_attachments(
        fact, [gap], [attachment], tmp_path
    )
    assert result["decision"] == "eligible"
    assert result["attachments"]["accepted"] == [attachment["attachment_id"]]
    assert result["promotion_performed"] is False
    assert fact == original


def test_tampering_and_unauthorized_dimension_fail_closed(tmp_path):
    fact, gap, attachment = _inputs(tmp_path)
    attachment["satisfied_dimensions"] = ["scope_binding"]
    reasons = validate_postvalidation_attachment(attachment, fact, gap, tmp_path)
    assert "ATTACHMENT_INTEGRITY_SIGNATURE_INVALID" in reasons
    assert "ATTACHMENT_DIMENSION_CLAIM_UNAUTHORIZED" in reasons


def test_fact_gap_and_diagnostic_hash_mismatches_are_rejected(tmp_path):
    fact, gap, attachment = _inputs(tmp_path)
    attachment["parent_fact_id"] = "fact-wrong"
    attachment["parent_gap_id"] = "gap-wrong"
    attachment["diagnostic"]["sha256"] = "0" * 64
    reasons = validate_postvalidation_attachment(attachment, fact, gap, tmp_path)
    assert "ATTACHMENT_FACT_MISMATCH" in reasons
    assert "ATTACHMENT_GAP_MISMATCH" in reasons
    assert "ATTACHMENT_DIAGNOSTIC_HASH_MISMATCH" in reasons


def test_period_eligibility_shape_normalizes_without_losing_raw_payload(tmp_path):
    payload = {
        "case_id": "period-a",
        "contract_passed": True,
        "execution_error": None,
        "observed": {
            "eligibility": "eligible",
            "binding_type": "period",
            "blocking_reasons": [],
        },
    }
    (tmp_path / "period.json").write_text(json.dumps(payload))
    envelope = build_diagnostic_result_envelope(
        payload=payload,
        diagnostic_path="period.json",
        parent_fact_id="fact-a",
        parent_gap_id="gap-a",
        case_id="period-a",
        root=tmp_path,
    )
    assert envelope["normalized_status"] == "passed"
    assert envelope["identity_binding"]["fact_id_source"] == "frozen_manifest"
    assert envelope["raw_payload"] == payload


def test_envelope_fails_closed_on_identity_conflict_or_blockers(tmp_path):
    payload = {
        "contract_passed": True,
        "observed": {
            "status": "passed",
            "fact_record_id": "fact-wrong",
            "gap_id": "gap-a",
            "blocking_reasons": ["ambiguous"],
        },
    }
    (tmp_path / "conflict.json").write_text(json.dumps(payload))
    envelope = build_diagnostic_result_envelope(
        payload=payload,
        diagnostic_path="conflict.json",
        parent_fact_id="fact-a",
        parent_gap_id="gap-a",
        case_id="case-a",
        root=tmp_path,
    )
    assert envelope["normalized_status"] == "blocked"
    assert envelope["blocking_reasons"] == [
        "component_reported_blocking_reasons",
        "parent_fact_identity_conflict",
    ]


def test_attachment_validator_accepts_signed_normalized_envelope(tmp_path):
    fact, gap, _ = _inputs(tmp_path)
    raw = json.loads((tmp_path / "diagnostic.json").read_text())
    envelope = build_diagnostic_result_envelope(
        payload=raw,
        diagnostic_path="diagnostic.json",
        parent_fact_id="fact-a",
        parent_gap_id="gap-a",
        case_id="case-a",
        root=tmp_path,
    )
    (tmp_path / "envelope.json").write_text(json.dumps(envelope))
    attachment = build_postvalidation_attachment(
        fact=fact,
        gap=gap,
        diagnostic_path="envelope.json",
        satisfied_dimensions=["field_or_cell_binding"],
        remaining_dimensions=[],
        root=tmp_path,
    )
    assert validate_postvalidation_attachment(attachment, fact, gap, tmp_path) == []


def test_single_raw_result_wrapper_normalizes_and_preserves_outer_payload(tmp_path):
    payload = {
        "contract_passed": True,
        "status": "completed",
        "raw_result": {
            "status": "passed",
            "fact_record_id": "fact-a",
            "gap_id": "gap-a",
            "blocking_reasons": [],
        },
    }
    (tmp_path / "wrapped.json").write_text(json.dumps(payload))
    envelope = build_diagnostic_result_envelope(
        payload=payload,
        diagnostic_path="wrapped.json",
        parent_fact_id="fact-a",
        parent_gap_id="gap-a",
        case_id="case-a",
        root=tmp_path,
    )
    assert envelope["normalized_status"] == "passed"
    assert envelope["identity_binding"]["component_result_path"] == "raw_result"
    assert envelope["raw_payload"] == payload


def test_payload_mismatch_fails_closed(tmp_path):
    stored = {"contract_passed": True, "raw_result": {"status": "passed"}}
    supplied = copy.deepcopy(stored)
    supplied["raw_result"]["status"] = "blocked"
    (tmp_path / "stored.json").write_text(json.dumps(stored))
    envelope = build_diagnostic_result_envelope(
        payload=supplied,
        diagnostic_path="stored.json",
        parent_fact_id="fact-a",
        parent_gap_id="gap-a",
        case_id="case-a",
        root=tmp_path,
    )
    assert envelope["normalized_status"] == "blocked"
    assert "parent_payload_mismatch" in envelope["blocking_reasons"]


def test_invalid_raw_result_wrappers_fail_closed(tmp_path):
    payloads = [
        {"contract_passed": True, "raw_result": "passed"},
        {
            "contract_passed": True,
            "raw_result": {"raw_result": {"status": "passed"}},
        },
    ]
    expected_reasons = ["raw_result_not_object", "nested_raw_result_not_allowed"]
    for index, (payload, expected) in enumerate(
        zip(payloads, expected_reasons, strict=True)
    ):
        name = f"invalid-{index}.json"
        (tmp_path / name).write_text(json.dumps(payload))
        envelope = build_diagnostic_result_envelope(
            payload=payload,
            diagnostic_path=name,
            parent_fact_id="fact-a",
            parent_gap_id="gap-a",
            case_id="case-a",
            root=tmp_path,
        )
        assert envelope["normalized_status"] == "blocked"
        assert expected in envelope["blocking_reasons"]


def test_raw_result_outer_failure_and_inner_identity_conflict_fail_closed(tmp_path):
    payload = {
        "contract_passed": False,
        "execution_error": "archive failed",
        "raw_result": {
            "status": "passed",
            "fact_record_id": "fact-wrong",
            "gap_id": "gap-a",
        },
    }
    (tmp_path / "outer-failure.json").write_text(json.dumps(payload))
    envelope = build_diagnostic_result_envelope(
        payload=payload,
        diagnostic_path="outer-failure.json",
        parent_fact_id="fact-a",
        parent_gap_id="gap-a",
        case_id="case-a",
        root=tmp_path,
    )
    assert envelope["normalized_status"] == "blocked"
    assert set(envelope["blocking_reasons"]) >= {
        "parent_contract_not_passed",
        "parent_execution_error",
        "parent_fact_identity_conflict",
    }
