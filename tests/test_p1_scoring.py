from esg_reliable_discovery.p1_scoring import (
    score_candidate_against_synthetic_reference,
    score_v04_finalized_output,
)


def _reference(status="verified_fact", value=10):
    return {
        "task_id": "P1-01-2", "reference_status": "verified", "answer_status": status,
        "answer": value, "normalized_value": value, "normalized_unit": "million gallons",
        "subject": "Apple Inc.", "scope_boundary": "supplier facilities", "period": "FY2024",
        "evidence": [{"document_id": "DOC", "pdf_page": 49}],
    }


def _candidate(status="verified_fact", value=10):
    return {
        "task_id": "P1-01-2", "answer_status": status, "answer": value,
        "normalized_value": value, "normalized_unit": "million gallons",
        "subject": "Apple Inc.", "scope_boundary": "supplier facilities", "period": "FY2024",
        "evidence": [{"source_id": "DOC", "page": 49}],
    }


def test_scores_dimensions_without_aggregate():
    result = score_candidate_against_synthetic_reference(_candidate(), _reference())
    assert result["dimensions"]["answer_status_exact"] is True
    assert result["dimensions"]["normalized_value_match"] is True
    assert result["dimensions"]["evidence_locator_recall"] == 1.0
    assert result["aggregate_score"] is None


def test_numeric_string_with_percent_is_compared_numerically():
    candidate = _candidate(value="10%")
    result = score_candidate_against_synthetic_reference(candidate, _reference(value=10))
    assert result["dimensions"]["normalized_value_match"] is True


def test_scores_correct_abstention():
    reference = _reference("insufficient_information", None)
    candidate = _candidate("insufficient_information", None)
    candidate["answer"] = None
    result = score_candidate_against_synthetic_reference(candidate, reference)
    assert result["dimensions"]["abstention_correct"] is True
    assert result["dimensions"]["normalized_value_match"] is None
    assert result["dimensions"]["normalized_unit_exact"] is None


def test_conflict_scores_both_source_locators_without_single_value():
    reference = _reference("conflict", 10)
    reference["controlled_intervention_id"] = "P1-CI-001"
    candidate = _candidate("conflict", None)
    candidate["normalized_value"] = None
    candidate["evidence"].append({"source_id": "P1-CI-001", "page": 1})
    result = score_candidate_against_synthetic_reference(candidate, reference)
    assert result["dimensions"]["normalized_value_match"] is None
    assert result["dimensions"]["normalized_unit_exact"] is None
    assert result["dimensions"]["evidence_locator_precision"] == 1.0
    assert result["dimensions"]["evidence_locator_recall"] == 1.0


def test_v04_scores_model_and_framework_calculation_separately():
    reference = _reference("verified_fact", -3.02)
    finalized = {
        "model_output": _candidate("conflict", -3.06),
        "resolved_evidence": [
            {"source_id": "DOC", "page": 49, "verbatim_excerpt": "values"}
        ],
        "deterministic_calculation": {"result": -3.016192},
        "model_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }
    result = score_v04_finalized_output(finalized, reference)
    assert result["model_dimensions"]["answer_status_exact"] is False
    assert result["model_dimensions"]["normalized_value_match"] is False
    assert result["framework_dimensions"]["deterministic_calculation_value_match"] is True
    assert result["aggregate_score"] is None
