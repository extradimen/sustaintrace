from __future__ import annotations

from typing import Any

from .v17_causal_epistemics import classify_attribution_and_causal_identification
from .v17_multifragment import project_grounded_string_fragments
from .v17_threshold import compare_recalculated_to_issuer_threshold


def run_v17_postprocess(
    *, stage_a_output: dict[str, Any], evidence: list[dict[str, Any]],
    threshold_claim: dict[str, Any] | None = None,
    issuer_attribution: str | None = None,
    identification_evidence: list[dict[str, Any]] | None = None,
    string_fragments: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute frozen v1.7 deterministic operations without altering candidates."""
    operations: dict[str, Any] = {}
    if threshold_claim is not None:
        calculation = stage_a_output.get("deterministic_calculation")
        if not calculation:
            raise ValueError("v17_threshold_requires_stage_a_calculation")
        operations["inequality_threshold_comparison"] = (
            compare_recalculated_to_issuer_threshold(
                deterministic_calculation=calculation,
                issuer_claim=threshold_claim,
            )
        )
    if issuer_attribution is not None:
        operations["attribution_and_causal_identification"] = (
            classify_attribution_and_causal_identification(
                issuer_attribution=issuer_attribution,
                evidence=evidence,
                identification_evidence=identification_evidence,
            )
        )
    if string_fragments is not None:
        operations["multi_fragment_string_projection"] = (
            project_grounded_string_fragments(
                fragments=string_fragments,
                evidence=evidence,
            )
        )
    if not operations:
        raise ValueError("v17_no_postprocess_operation_requested")
    return {
        "pipeline_version":"ESG-RD-v1.7-DETERMINISTIC-POSTPROCESS",
        "model_inference_performed":False,
        "candidate_output_modified":False,
        "operations":operations,
    }
