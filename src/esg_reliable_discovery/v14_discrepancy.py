from __future__ import annotations

import math
import re
from typing import Any


def evaluate_within_report_numeric_discrepancy(
    *,
    components: list[dict[str, Any]],
    reported_total: dict[str, Any],
    available_handles: list[dict[str, Any]],
    absolute_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Compare grounded components with a grounded total from one report.

    This is a framework-owned arithmetic operation: it does not infer missing
    components, convert units, or repair model-provided values.
    """
    if len(components) < 2:
        raise ValueError("discrepancy_requires_at_least_two_components")
    index = {item["handle"]: item for item in available_handles}
    if len(index) != len(available_handles):
        raise ValueError("available_handle_ids_must_be_unique")
    observations = [*components, reported_total]
    source_ids = set()
    units = set()
    resolved = []
    for observation in observations:
        handle_id = observation["evidence_handle"]
        if handle_id not in index:
            raise ValueError(f"unknown_evidence_handle:{handle_id}")
        handle = index[handle_id]
        source_ids.add(handle["source_id"])
        units.add(observation["normalized_unit"])
        value = float(observation["value"])
        text = " ".join(
            filter(None, [handle.get("normalized_text"), handle.get("table_header_context")])
        )
        numeric_tokens = [
            float(token.replace(",", ""))
            for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
        ]
        if not any(
            math.isclose(value, token, rel_tol=1e-9, abs_tol=1e-9)
            for token in numeric_tokens
        ):
            raise ValueError(f"discrepancy_value_not_grounded:{handle_id}")
        resolved.append({"observation": observation, "evidence": handle})
    if len(source_ids) != 1:
        raise ValueError("discrepancy_requires_one_report_source")
    if len(units) != 1:
        raise ValueError("discrepancy_requires_identical_normalized_units")
    component_sum = math.fsum(float(item["value"]) for item in components)
    total = float(reported_total["value"])
    delta = component_sum - total
    return {
        "operation": "within_report_component_total_discrepancy",
        "source_id": next(iter(source_ids)),
        "normalized_unit": next(iter(units)),
        "component_sum": component_sum,
        "reported_total": total,
        "signed_delta": delta,
        "absolute_delta": abs(delta),
        "is_discrepant": not math.isclose(
            component_sum, total, rel_tol=0.0, abs_tol=absolute_tolerance
        ),
        "absolute_tolerance": absolute_tolerance,
        "resolved_observations": resolved,
        "framework_owned_operation": True,
        "semantic_repair_applied": False,
    }
