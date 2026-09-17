import pytest

from esg_reliable_discovery.v3_tools import (
    evidence_handle_model_schema,
    resolve_evidence_handles,
    verify_deterministic_calculation,
)


def test_evidence_handle_schema_removes_model_control_of_immutable_locator():
    schema = {
        "title": "content",
        "$defs": {
            "evidence": {
                "type": "object",
                "properties": {"document_sha256": {"type": "string"}},
            }
        },
    }
    transformed = evidence_handle_model_schema(schema)
    properties = transformed["$defs"]["evidence"]["properties"]
    assert "source_handle" in properties
    assert "document_sha256" not in properties
    assert "page" not in properties


def test_handle_resolution_is_deterministic_and_preserves_model_payload():
    model = {
        "supporting_evidence": [
            {
                "source_handle": "S001",
                "location": "table",
                "excerpt": "value",
                "evidence_strength": "direct",
            }
        ],
        "contrary_evidence": [],
    }
    manifest = {
        "evidence_handles": [
            {
                "source_handle": "S001",
                "document_id": "DOC",
                "document_sha256": "a" * 64,
                "page": 7,
            }
        ]
    }
    resolved = resolve_evidence_handles(model, manifest)
    assert model["supporting_evidence"][0]["source_handle"] == "S001"
    assert resolved["supporting_evidence"][0]["document_id"] == "DOC"
    assert resolved["supporting_evidence"][0]["page"] == 7


def test_unknown_evidence_handle_is_a_hard_failure():
    with pytest.raises(ValueError, match="unknown_evidence_handle"):
        resolve_evidence_handles(
            {"supporting_evidence": [{"source_handle": "S999"}], "contrary_evidence": []},
            {"evidence_handles": []},
        )


def test_deterministic_calculator_detects_wrong_sign_without_repairing_model_result():
    card = {
        "calculation": {
            "inputs": ["FY2024: 16", "FY2023: 21"],
            "result": 23.8095238095,
            "unit": "%",
        }
    }
    result = verify_deterministic_calculation(card, "percent_change_current_prior")
    assert result["tool_result"] == pytest.approx(-23.8095238095)
    assert result["consistent"] is False
    assert result["model_output_modified"] is False
