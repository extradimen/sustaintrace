from __future__ import annotations

import math
import re
from typing import Any


def compose_reported_and_recalculated_comparison(
    *,
    deterministic_calculation: dict[str, Any],
    reported_observation: dict[str, Any],
    available_handles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep a framework calculation and issuer-reported value as distinct claims."""
    if deterministic_calculation.get("executed_by") != "deterministic_framework":
        raise ValueError("v16_requires_framework_calculation")
    if deterministic_calculation.get("operation") != "percentage_change":
        raise ValueError("v16_requires_percentage_change")
    index = {item["handle"]: item for item in available_handles}
    if len(index) != len(available_handles):
        raise ValueError("v16_available_handles_must_be_unique")
    handle_id = reported_observation["evidence_handle"]
    if handle_id not in index:
        raise ValueError(f"v16_unknown_evidence_handle:{handle_id}")
    evidence = index[handle_id]
    reported = float(reported_observation["value"])
    tokens = [
        float(token.replace(",", ""))
        for token in re.findall(
            r"[-+]?\d[\d,]*(?:\.\d+)?",
            " ".join(
                filter(
                    None,
                    [
                        evidence.get("normalized_text"),
                        evidence.get("table_header_context"),
                    ],
                )
            ),
        )
    ]
    if not any(math.isclose(abs(reported), token) for token in tokens):
        raise ValueError(f"v16_reported_value_not_grounded:{handle_id}")
    recalculated = float(deterministic_calculation["result"])
    signed_reported = (
        -abs(reported)
        if reported_observation.get("direction") == "decrease"
        else reported
    )
    delta = recalculated - signed_reported
    return {
        "operation": "reported_vs_recalculated_percentage_comparison",
        "recalculated_observation": {
            "value": recalculated,
            "provenance": "deterministic_framework_from_displayed_inputs",
        },
        "issuer_reported_observation": {
            "value": signed_reported,
            "evidence_handle": handle_id,
            "provenance": "issuer_reported_literal",
        },
        "signed_percentage_point_delta": delta,
        "absolute_percentage_point_delta": abs(delta),
        "comparison_state": (
            "consistent_within_tolerance"
            if math.isclose(recalculated, signed_reported, abs_tol=1e-9)
            else "displayed_inputs_do_not_reproduce_reported_percentage"
        ),
        "values_forced_to_agree": False,
        "framework_owned_operation": True,
    }
