from esg_reliable_discovery.scoring_v2 import score_finding_card_v2


def test_v2_scoring_separates_value_unit_and_semantic_field_overlap():
    candidate = {
        "finding_type": "extracted_fact",
        "claim_level": "L1",
        "status": "verified",
        "metric": {
            "name": "project capacity",
            "reported_value": 6.6,
            "unit": "megawatt",
            "subject": "Clearloop project",
            "boundary": "Mississippi Delta",
            "period": "Not Reported",
        },
        "supporting_evidence": [{"document_id": "D", "document_sha256": "a" * 64, "page": 1}],
        "contrary_evidence": [],
    }
    gold = {
        "task_id": "T",
        "finding_type": "extracted_fact",
        "claim_level": "L1",
        "status": "verified",
        "metric": {
            "name": "Clearloop project capacity",
            "reported_value": 6.6,
            "unit": "MW",
            "subject": "Clearloop project",
            "boundary": "Mississippi Delta region",
            "period": "2024 report",
        },
        "supporting_evidence": [{"document_id": "D", "document_sha256": "a" * 64, "page": 1}],
        "contrary_evidence": [],
    }
    result = score_finding_card_v2(candidate, gold, {"type": "object"})["dimensions"]
    assert result["reported_value_accuracy"] == 1
    assert result["unit_canonical_accuracy"] == 1
    assert result["metric_name_token_jaccard"] == 2 / 3
    assert result["boundary_token_jaccard"] == 2 / 3
    assert result["period_token_jaccard"] == 0
    assert result["supporting_evidence_locator_accuracy"] == 1
