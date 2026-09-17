from __future__ import annotations

from typing import Any

from .v16_comparison import compose_reported_and_recalculated_comparison
from .v16_conflict import classify_scope_conflict_and_causality


def run_v16_postprocess(
    *,
    stage_a_output: dict[str, Any],
    available_handles: list[dict[str, Any]],
    comparison_spec: dict[str, Any] | None = None,
    stage_b_output: dict[str, Any] | None = None,
    conflict_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run frozen, deterministic v1.6 postprocessors without model inference."""
    result: dict[str, Any] = {
        "pipeline_version": "ESG-RD-v1.6-DETERMINISTIC-POSTPROCESS",
        "model_inference_performed": False,
        "candidate_output_modified": False,
        "operations": {},
    }
    if comparison_spec is not None:
        calculation = stage_a_output.get("deterministic_calculation")
        if not calculation:
            raise ValueError("v16_comparison_requires_stage_a_calculation")
        result["operations"]["reported_vs_recalculated"] = (
            compose_reported_and_recalculated_comparison(
                deterministic_calculation=calculation,
                reported_observation=comparison_spec["reported_observation"],
                available_handles=available_handles,
            )
        )
    if conflict_spec is not None:
        if stage_b_output is None:
            raise ValueError("v16_conflict_requires_stage_b_output")
        claims = {
            item["slot_id"]: item for item in stage_b_output["validated_claims"]
        }
        left_id = conflict_spec["left_slot_id"]
        right_id = conflict_spec["right_slot_id"]
        if left_id not in claims or right_id not in claims:
            raise ValueError("v16_conflict_slot_missing")
        result["operations"]["scope_conflict_and_causality"] = (
            classify_scope_conflict_and_causality(
                left_observation=claims[left_id],
                right_observation=claims[right_id],
                proposed_causal_explanation=conflict_spec.get(
                    "proposed_causal_explanation"
                ),
                evidence=available_handles,
            )
        )
    if not result["operations"]:
        raise ValueError("v16_no_postprocess_operation_requested")
    return result
