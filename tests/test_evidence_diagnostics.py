from esg_reliable_discovery.evidence_diagnostics import diagnose_evidence_state


def test_distinguishes_issuer_non_disclosure() -> None:
    result = diagnose_evidence_state(
        issuer_answer_status="not_disclosed",
        expected_anchors=["HC-BP-250a.4"],
        raw_page_text="HC-BP-250a.4 — Not reported",
        parsed_page_text="HC-BP-250a.4 — Not reported",
        retrieved_evidence_text="HC-BP-250a.4 — Not reported",
    )
    assert result["state"] == "not_disclosed_by_issuer"
    assert result["non_disclosure_marker"] == "not reported"


def test_distinguishes_parser_loss() -> None:
    result = diagnose_evidence_state(
        issuer_answer_status="answerable",
        expected_anchors=["61,754", "44,190"],
        raw_page_text="2020 61,754 metric tCO2e; 2024 44,190 metric tCO2e",
        parsed_page_text="2020 metric tCO2e; 2024 tCO2e",
        retrieved_evidence_text="2020 metric tCO2e; 2024 tCO2e",
    )
    assert result["state"] == "parser_structure_unrecoverable"


def test_distinguishes_retrieval_miss() -> None:
    result = diagnose_evidence_state(
        issuer_answer_status="answerable",
        expected_anchors=["358"],
        raw_page_text="Total emissions 358",
        parsed_page_text="Total emissions 358",
        retrieved_evidence_text="Unrelated narrative",
    )
    assert result["state"] == "retrieval_miss"


def test_supported_evidence_takes_precedence() -> None:
    result = diagnose_evidence_state(
        issuer_answer_status="answerable",
        expected_anchors=["13,891"],
        raw_page_text="Scope 3 13,891",
        parsed_page_text="Scope 3 13,891",
        retrieved_evidence_text="Scope 3 13,891",
    )
    assert result["state"] == "supported_in_retrieved_evidence"
    assert result["hidden_anchor_injection_allowed"] is False


def test_value_present_but_table_binding_lost_is_parser_failure() -> None:
    result = diagnose_evidence_state(
        issuer_answer_status="answerable",
        expected_anchors=["13,891"],
        raw_page_text="Scope 3 | Gross 2025 | 13,891",
        parsed_page_text="Scope 3 | SBTi 2025 | 13,891",
        retrieved_evidence_text="Scope 3 | SBTi 2025 | 13,891",
        structure_required=True,
        raw_structure_supported=True,
        parsed_structure_supported=False,
        retrieved_structure_supported=False,
    )
    assert result["state"] == "parser_structure_unrecoverable"
