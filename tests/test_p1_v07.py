import pytest
from jsonschema import Draft202012Validator

from esg_reliable_discovery.p1_v07 import (
    finalize_v07_output,
    normalize_period_year,
    task_conditioned_schema_v07,
)


def _handles():
    return [
        {"handle": "M093-B0001", "source_id": "REPORT", "page": 93,
         "verbatim_text": "Official value 1,200,000 tCO2e",
         "normalized_text": "Official value 1,200,000 tCO2e"},
        {"handle": "I001-L0001", "source_id": "NOTE", "page": 1,
         "verbatim_text": "Analyst value 1,250,000 tCO2e",
         "normalized_text": "Analyst value 1,250,000 tCO2e"},
    ]


def test_v07_absent_requires_null_answer_and_empty_evidence():
    schema = task_conditioned_schema_v07("abstention", ["M093-B0001"])
    valid = {
        "answer": None, "normalized_value": None, "evidence_handles": [],
    }
    assert not list(Draft202012Validator(schema).iter_errors(valid))
    invalid = {**valid, "answer": "insufficient_information"}
    assert list(Draft202012Validator(schema).iter_errors(invalid))


def test_v071_abstention_rejects_redundant_metadata():
    schema = task_conditioned_schema_v07("abstention", ["M093-B0001"])
    output = {
        "answer": None, "normalized_value": None, "evidence_handles": [],
        "task_id": "P1-01-1",
    }
    assert list(Draft202012Validator(schema).iter_errors(output))


def test_v072_cross_page_requires_only_answer_and_grounded_handles():
    schema = task_conditioned_schema_v07(
        "cross_page_relation", ["M093-B0001", "I001-L0001"]
    )
    output = {
        "answer": "The 61% result exceeded the 60% target.",
        "evidence_handles": ["M093-B0001", "I001-L0001"],
    }
    assert not list(Draft202012Validator(schema).iter_errors(output))
    result = finalize_v07_output(output, "cross_page_relation", _handles())
    assert result["framework_evidence_state"] == "supported"


def test_same_document_source_conflict_uses_relational_evidence_schema():
    schema = task_conditioned_schema_v07(
        "source_conflict", ["M093-B0001", "I001-L0001"]
    )
    output = {
        "answer": "The displayed component sum differs from the aggregate.",
        "evidence_handles": ["M093-B0001", "I001-L0001"],
    }
    assert not list(Draft202012Validator(schema).iter_errors(output))
    result = finalize_v07_output(output, "source_conflict", _handles())
    assert result["framework_evidence_state"] == "supported"


def test_v072_cross_page_rejects_answer_without_evidence():
    schema = task_conditioned_schema_v07("cross_page_relation", ["M021-B0001"])
    output = {"answer": "unsupported", "evidence_handles": []}
    assert list(Draft202012Validator(schema).iter_errors(output))


def test_v075_scope_boundary_uses_minimal_relational_contract():
    schema = task_conditioned_schema_v07("scope_subject_boundary", ["M049-B0031"])
    output = {
        "answer": "In 2024, 161 million gallons were avoided at offices and data centers.",
        "evidence_handles": ["M049-B0031"],
    }
    assert not list(Draft202012Validator(schema).iter_errors(output))


def test_v076_direct_extraction_uses_stage_a_minimal_contract():
    schema = task_conditioned_schema_v07("direct_extraction", ["M200-T0001-R0008"])
    output = {
        "answer": "BASF reported 0.027 million metric tons CO2e in 2024.",
        "evidence_handles": ["M200-T0001-R0008"],
    }
    assert not list(Draft202012Validator(schema).iter_errors(output))


def test_v07_supported_requires_evidence():
    schema = task_conditioned_schema_v07("direct_extraction", ["M093-B0001"])
    output = {
        "task_id": "P1-02-2", "subject": "x", "scope_boundary": None,
        "period": "2024", "answer": 1.2, "normalized_value": 1.2,
        "normalized_unit": "t", "evidence_handles": [],
    }
    assert list(Draft202012Validator(schema).iter_errors(output))


def test_v07_framework_derives_grounded_source_conflict():
    output = {
        "source_claims": [
            {"source_id": "REPORT", "evidence_handle": "M093-B0001",
             "normalized_value": 1200000, "normalized_unit": "tCO2e"},
            {"source_id": "NOTE", "evidence_handle": "I001-L0001",
             "normalized_value": 1250000, "normalized_unit": "tCO2e"},
        ],
    }
    result = finalize_v07_output(output, "controlled_conflict", _handles())
    assert result["framework_evidence_state"] == "contradictory_sources"
    assert all(claim["grounded"] for claim in result["grounded_source_claims"])


def test_v07_rejects_claim_source_mismatch():
    output = {
        "source_claims": [
            {"source_id": "NOTE", "evidence_handle": "M093-B0001",
             "normalized_value": 1200000, "normalized_unit": "tCO2e"},
            {"source_id": "REPORT", "evidence_handle": "I001-L0001",
             "normalized_value": 1250000, "normalized_unit": "tCO2e"},
        ],
    }
    with pytest.raises(ValueError, match="claim_source_mismatch"):
        finalize_v07_output(output, "controlled_conflict", _handles())


def test_v07_rejects_ungrounded_numeric_claim():
    output = {
        "source_claims": [
            {"source_id": "REPORT", "evidence_handle": "M093-B0001",
             "normalized_value": 99, "normalized_unit": "tCO2e"},
            {"source_id": "NOTE", "evidence_handle": "I001-L0001",
             "normalized_value": 1250000, "normalized_unit": "tCO2e"},
        ],
    }
    with pytest.raises(ValueError, match="claim_value_not_grounded"):
        finalize_v07_output(output, "controlled_conflict", _handles())


def test_v074_percentage_change_schema_rejects_semantic_roles():
    schema = task_conditioned_schema_v07(
        "deterministic_calculation", ["M093-B0001"]
    )
    base = {}
    wrong = {
        **base,
        "calculation_request": {
            "operation": "percentage_change",
            "inputs": [
                {"value": 91.64, "evidence_handle": "M093-B0001", "role": "numerator"},
                {"value": 94.49, "evidence_handle": "M093-B0001", "role": "denominator"},
            ],
        },
    }
    assert list(Draft202012Validator(schema).iter_errors(wrong))


def test_v074_percentage_change_uses_distinct_period_years():
    schema = task_conditioned_schema_v07(
        "deterministic_calculation", ["M093-B0001"]
    )
    valid = {
        "calculation_request": {
            "operation": "percentage_change",
            "inputs": [
                {"value": 91.64, "evidence_handle": "M093-B0001", "role": "current"},
                {"value": 94.49, "evidence_handle": "M093-B0001", "role": "prior"},
            ],
        },
    }
    assert list(Draft202012Validator(schema).iter_errors(valid))
    valid["calculation_request"]["inputs"] = [
        {"value": 1200000, "evidence_handle": "M093-B0001", "period_year": 2024},
        {"value": 1250000, "evidence_handle": "M093-B0001", "period_year": 2023},
    ]
    assert not list(Draft202012Validator(schema).iter_errors(valid))


def test_v074_framework_assigns_roles_from_grounded_years():
    handles = [{
        "handle": "M200-T0001-R0032", "source_id": "BASF", "page": 200,
        "verbatim_text": "Total | 91.64 | 94.49",
        "normalized_text": "Total | 91.64 | 94.49",
        "table_header_context": "2024 | 2023",
    }]
    output = {
        "calculation_request": {
            "operation": "percentage_change",
            "inputs": [
                {"value": 94.49, "evidence_handle": "M200-T0001-R0032",
                 "period_year": 2023},
                {"value": 91.64, "evidence_handle": "M200-T0001-R0032",
                 "period_year": 2024},
            ],
        },
    }
    result = finalize_v07_output(output, "deterministic_calculation", handles)
    assignment = result["framework_period_role_assignment"]
    assert assignment["current_year"] == 2024
    assert assignment["prior_year"] == 2023
    assert assignment["model_period_literals"] == [2023, 2024]
    assert result["deterministic_calculation"]["result"] == pytest.approx(-3.01619219)


def test_v14_normalizes_controlled_fiscal_year_literals_and_preserves_originals():
    assert normalize_period_year("FY23") == (2023, "FY23")
    handles = [{
        "handle": "M010-T0001-R0002", "source_id": "REPORT", "page": 10,
        "verbatim_text": "Revenue | FY23 100 | FY24 125",
        "normalized_text": "Revenue | FY23 100 | FY24 125",
        "table_header_context": "FY23 | FY24",
    }]
    output = {
        "calculation_request": {
            "operation": "percentage_change",
            "inputs": [
                {"value": 100, "evidence_handle": "M010-T0001-R0002",
                 "period_year": "FY23"},
                {"value": 125, "evidence_handle": "M010-T0001-R0002",
                 "period_year": "FY24"},
            ],
        },
    }
    schema = task_conditioned_schema_v07(
        "deterministic_calculation", ["M010-T0001-R0002"]
    )
    assert not list(Draft202012Validator(schema).iter_errors(output))
    result = finalize_v07_output(output, "deterministic_calculation", handles)
    assignment = result["framework_period_role_assignment"]
    assert assignment["current_year"] == 2024
    assert assignment["prior_year"] == 2023
    assert assignment["model_period_literals"] == ["FY23", "FY24"]
    assert result["deterministic_calculation"]["result"] == pytest.approx(25.0)


def test_v091_calculation_rejects_framework_owned_metadata():
    schema = task_conditioned_schema_v07(
        "deterministic_calculation", ["M093-B0001"]
    )
    output = {
        "task_id": "P1-02-1",
        "calculation_request": None,
    }
    assert list(Draft202012Validator(schema).iter_errors(output))


def test_v091_conflict_uses_only_source_claims():
    schema = task_conditioned_schema_v07(
        "controlled_conflict", ["M093-B0001", "I001-L0001"]
    )
    output = {
        "source_claims": [
            {"source_id": "REPORT", "evidence_handle": "M093-B0001",
             "normalized_value": 1200000, "normalized_unit": "tCO2e"},
            {"source_id": "NOTE", "evidence_handle": "I001-L0001",
             "normalized_value": 1250000, "normalized_unit": "tCO2e"},
        ],
    }
    assert not list(Draft202012Validator(schema).iter_errors(output))
    assert list(Draft202012Validator(schema).iter_errors({**output, "period": "FY2024"}))
