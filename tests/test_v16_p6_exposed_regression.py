import math

from esg_reliable_discovery.v16_comparison import (
    compose_reported_and_recalculated_comparison,
)
from esg_reliable_discovery.v16_conflict import classify_scope_conflict_and_causality


def test_p6_rounded_values_and_reported_change_remain_distinct():
    result = compose_reported_and_recalculated_comparison(
        deterministic_calculation={
            "operation": "percentage_change",
            "result": (0.43 - 0.48) / 0.48 * 100,
            "executed_by": "deterministic_framework",
        },
        reported_observation={
            "value": 12,
            "direction": "decrease",
            "evidence_handle": "E1",
        },
        available_handles=[{
            "handle": "E1",
            "normalized_text": "Gross Scope 1 | 0.43 | 0.48 | (12)%",
        }],
    )
    assert result["comparison_state"] == (
        "displayed_inputs_do_not_reproduce_reported_percentage"
    )
    assert math.isclose(result["absolute_percentage_point_delta"], 1.5833333333333357)
    assert result["values_forced_to_agree"] is False


def test_p6_scope_resolves_conflict_but_contractor_cause_is_unsupported():
    result = classify_scope_conflict_and_causality(
        left_observation={"value": False, "scope_id": "continuing_unilever"},
        right_observation={"value": True, "scope_id": "ice_cream"},
        proposed_causal_explanation="because the fatality was a contractor, not an employee",
        evidence=[
            {"handle": "E1", "verbatim_text": "Fatalities: allocated case by case."},
            {"handle": "E2", "verbatim_text": "A contractor died at an Ice Cream factory."},
        ],
    )
    assert result["conflict_state"] == "scope_resolves_apparent_conflict"
    assert result["causal_explanation_state"] == "causal_explanation_unsupported"


def test_exact_causal_statement_can_be_supported_without_inference():
    result = classify_scope_conflict_and_causality(
        left_observation={"value": 1, "scope_id": "same"},
        right_observation={"value": 2, "scope_id": "same"},
        proposed_causal_explanation="increase was caused by acquisitions",
        evidence=[{
            "handle": "E1",
            "verbatim_text": "The increase was caused by acquisitions during the year.",
        }],
    )
    assert result["conflict_state"] == "unresolved_same_scope_value_conflict"
    assert result["causal_explanation_state"] == "causal_explanation_verbatim_supported"
