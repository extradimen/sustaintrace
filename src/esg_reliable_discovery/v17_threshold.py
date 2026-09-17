from __future__ import annotations

from typing import Any


def compare_recalculated_to_issuer_threshold(
    *, deterministic_calculation: dict[str, Any], issuer_claim: dict[str, Any]
) -> dict[str, Any]:
    """Compare a deterministic percentage change with an issuer inequality claim."""
    if deterministic_calculation.get("executed_by") != "deterministic_framework":
        raise ValueError("v17_requires_framework_calculation")
    if deterministic_calculation.get("operation") != "percentage_change":
        raise ValueError("v17_requires_percentage_change")
    operator = issuer_claim.get("operator")
    if operator not in {"more_than", "at_least", "less_than", "at_most"}:
        raise ValueError("v17_unsupported_threshold_operator")
    threshold = abs(float(issuer_claim["threshold_percent"]))
    recalculated = float(deterministic_calculation["result"])
    magnitude = abs(recalculated)
    comparisons = {
        "more_than": magnitude > threshold,
        "at_least": magnitude >= threshold,
        "less_than": magnitude < threshold,
        "at_most": magnitude <= threshold,
    }
    return {
        "operation":"recalculated_percentage_vs_issuer_inequality_threshold",
        "recalculated_value_percent":recalculated,
        "recalculated_magnitude_percent":magnitude,
        "issuer_operator":operator,
        "issuer_threshold_percent":threshold,
        "comparison_state":(
            "recalculated_value_satisfies_issuer_threshold"
            if comparisons[operator]
            else "recalculated_value_does_not_satisfy_issuer_threshold"
        ),
        "issuer_claim_converted_to_exact_value":False,
        "framework_owned_operation":True,
    }
