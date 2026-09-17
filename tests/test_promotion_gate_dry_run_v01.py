from pathlib import Path

from esg_reliable_discovery.promotion_gate import evaluate_promotion_dry_run


def _fact(tmp_path: Path, *, complete: bool = True):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"frozen")
    import hashlib

    return {
        "record_id": "fact-test",
        "trust_tier": "C",
        "value": "95%",
        "predicate": {"canonical_key": "target"},
        "subject": {
            "document_metadata": [
                {
                    "local_path": "source.pdf",
                    "sha256": hashlib.sha256(b"frozen").hexdigest(),
                }
            ]
        },
        "evidence": [
            {
                "quote": "95%",
                "pdf_page": 1,
                "row_index": 2,
                "column_index": 3,
                "role": "signed_independent_assurance_scope",
            }
        ],
        "qualifiers": {
            "reference_period": 2025 if complete else None,
            "normalized_unit": "percent",
            "scope_boundary": "reported target",
            "calculation_expression": None,
        },
        "provenance": {"simulated": False},
    }


def test_complete_fact_is_eligible_but_never_promoted(tmp_path):
    result = evaluate_promotion_dry_run(_fact(tmp_path), [], tmp_path)
    assert result["decision"] == "eligible"
    assert result["promotion_performed"] is False
    assert result["rollback_plan"]["fact_record_unchanged"] is True


def test_missing_dimension_and_open_gap_fail_closed(tmp_path):
    result = evaluate_promotion_dry_run(
        _fact(tmp_path, complete=False), ["PERIOD_ATTACHMENT_INCOMPLETE"], tmp_path
    )
    assert result["decision"] == "blocked"
    assert "PERIOD_BINDING_INCOMPLETE" in result["blocking_reasons"]
    assert "OPEN_GAP:PERIOD_ATTACHMENT_INCOMPLETE" in result["blocking_reasons"]
