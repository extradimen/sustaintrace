from esg_reliable_discovery.knowledge_base import bind_fact_field_to_evidence


def fact(value, quotes):
    return {
        "record_id": "fact-" + "a" * 24,
        "value": value,
        "evidence": [
            {"source_id": "DOC", "pdf_page": 1, "quote": quote} for quote in quotes
        ],
    }


PASSED = {"source_grounding_status": "passed"}


def test_number_binding_requires_a_bounded_exact_literal():
    binding = bind_fact_field_to_evidence(fact(938, ["baseline 938", "value 1938"]), PASSED)
    assert binding["binding_status"] == "unique_literal"
    assert binding["matched_evidence_indices"] == [0]
    assert binding["promotion_eligible"] is False


def test_grouped_integer_variants_bind_but_remain_candidates():
    binding = bind_fact_field_to_evidence(fact(8151769, ["Scope 3 8,151,769 tCO2e"]), PASSED)
    assert binding["binding_status"] == "unique_literal"
    assert binding["promotion_eligible"] is False


def test_multiple_and_complex_values_fail_closed():
    multiple = bind_fact_field_to_evidence(fact(10, ["value 10", "target 10"]), PASSED)
    complex_value = bind_fact_field_to_evidence(fact(["a", "b"], ["a and b"]), PASSED)
    assert multiple["binding_status"] == "multiple_literal"
    assert complex_value["binding_status"] == "unsupported_complex_value"


def test_failed_source_grounding_blocks_field_binding():
    binding = bind_fact_field_to_evidence(
        fact("limited assurance", ["limited assurance"]),
        {"source_grounding_status": "failed_quote"},
    )
    assert binding["binding_status"] == "source_grounding_failed"
