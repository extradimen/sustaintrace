import pytest

from esg_reliable_discovery.v14_discrepancy import (
    evaluate_within_report_numeric_discrepancy,
)


def _handles():
    return [
        {"handle": "P050-C1", "source_id": "NESTLE-2024", "page": 50,
         "normalized_text": "Water discharged 52.9 million m3"},
        {"handle": "P050-C2", "source_id": "NESTLE-2024", "page": 50,
         "normalized_text": "Water consumed 45.0 million m3"},
        {"handle": "P050-T", "source_id": "NESTLE-2024", "page": 50,
         "normalized_text": "Total water withdrawn 97.9 million m3"},
    ]


def _observation(value, handle):
    return {"value": value, "normalized_unit": "million_m3", "evidence_handle": handle}


def test_v14_within_report_discrepancy_computes_without_semantic_repair():
    result = evaluate_within_report_numeric_discrepancy(
        components=[_observation(52.9, "P050-C1"), _observation(45.0, "P050-C2")],
        reported_total=_observation(97.9, "P050-T"),
        available_handles=_handles(),
    )
    assert result["component_sum"] == pytest.approx(97.9)
    assert result["signed_delta"] == pytest.approx(0.0)
    assert result["is_discrepant"] is False
    assert result["semantic_repair_applied"] is False


def test_v14_within_report_discrepancy_flags_difference():
    result = evaluate_within_report_numeric_discrepancy(
        components=[_observation(52.9, "P050-C1"), _observation(45.0, "P050-C2")],
        reported_total=_observation(95.6, "P050-T"),
        available_handles=[*_handles()[:2], {**_handles()[2], "normalized_text": "95.6"}],
    )
    assert result["signed_delta"] == pytest.approx(2.3)
    assert result["is_discrepant"] is True


def test_v14_discrepancy_rejects_cross_report_inputs():
    handles = _handles()
    handles[2] = {**handles[2], "source_id": "OTHER"}
    with pytest.raises(ValueError, match="one_report_source"):
        evaluate_within_report_numeric_discrepancy(
            components=[_observation(52.9, "P050-C1"), _observation(45.0, "P050-C2")],
            reported_total=_observation(97.9, "P050-T"),
            available_handles=handles,
        )


def test_v14_discrepancy_rejects_ungrounded_values():
    with pytest.raises(ValueError, match="value_not_grounded"):
        evaluate_within_report_numeric_discrepancy(
            components=[_observation(999, "P050-C1"), _observation(45.0, "P050-C2")],
            reported_total=_observation(97.9, "P050-T"),
            available_handles=_handles(),
        )
