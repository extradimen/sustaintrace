from __future__ import annotations

from typing import Any

from .v15_grounding import unicode_equivalent_substring


def classify_scope_conflict_and_causality(
    *,
    left_observation: dict[str, Any],
    right_observation: dict[str, Any],
    proposed_causal_explanation: str | None,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Separate scope-based reconciliation from an asserted causal explanation."""
    values_differ = left_observation["value"] != right_observation["value"]
    scopes_differ = left_observation["scope_id"] != right_observation["scope_id"]
    if not values_differ:
        conflict_state = "no_value_conflict"
    elif scopes_differ:
        conflict_state = "scope_resolves_apparent_conflict"
    else:
        conflict_state = "unresolved_same_scope_value_conflict"
    causal_state = "not_proposed"
    supporting_handles: list[str] = []
    if proposed_causal_explanation:
        supporting_handles = [
            item["handle"]
            for item in evidence
            if unicode_equivalent_substring(
                proposed_causal_explanation, item.get("verbatim_text", "")
            )
        ]
        causal_state = (
            "causal_explanation_verbatim_supported"
            if supporting_handles
            else "causal_explanation_unsupported"
        )
    return {
        "conflict_state": conflict_state,
        "values_differ": values_differ,
        "scopes_differ": scopes_differ,
        "causal_explanation_state": causal_state,
        "causal_supporting_handles": supporting_handles,
        "scope_resolution_does_not_imply_causality": True,
        "framework_owned_classification": True,
    }
