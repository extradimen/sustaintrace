import pytest

from esg_reliable_discovery.v16_postprocess import run_v16_postprocess


def test_combined_v16_postprocess_uses_frozen_specs():
    output = run_v16_postprocess(
        stage_a_output={
            "deterministic_calculation": {
                "operation": "percentage_change",
                "result": -10.416666666666664,
                "executed_by": "deterministic_framework",
            }
        },
        stage_b_output={
            "validated_claims": [
                {"slot_id": "left", "value": False, "scope_id": "continuing"},
                {"slot_id": "right", "value": True, "scope_id": "disposed"},
            ]
        },
        available_handles=[
            {"handle": "R", "normalized_text": "reported change (12)%"},
            {"handle": "C", "verbatim_text": "Fatalities allocated case by case"},
        ],
        comparison_spec={
            "reported_observation": {
                "value": 12,
                "direction": "decrease",
                "evidence_handle": "R",
            }
        },
        conflict_spec={
            "left_slot_id": "left",
            "right_slot_id": "right",
            "proposed_causal_explanation": "because worker was a contractor",
        },
    )
    assert output["candidate_output_modified"] is False
    assert len(output["operations"]) == 2
    conflict = output["operations"]["scope_conflict_and_causality"]
    assert conflict["conflict_state"] == "scope_resolves_apparent_conflict"
    assert conflict["causal_explanation_state"] == "causal_explanation_unsupported"


def test_v16_postprocess_requires_requested_operation():
    with pytest.raises(ValueError, match="v16_no_postprocess_operation_requested"):
        run_v16_postprocess(stage_a_output={}, available_handles=[])
