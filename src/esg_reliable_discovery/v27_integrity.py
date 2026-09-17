from __future__ import annotations

from typing import Any

from .v26_integrity import validate_candidate_handles_v26


def build_handle_alias_catalog_v27(handles: list[str]) -> dict[str, str]:
    """Create compact deterministic aliases without accepting approximate handles."""
    if not handles or len(handles) != len(set(handles)):
        raise ValueError("v27_handle_catalog_invalid")
    return {f"H{index:04d}": handle for index, handle in enumerate(handles, start=1)}


def resolve_handle_aliases_v27(
    aliases: list[str], catalog: dict[str, str]
) -> tuple[list[str], dict[str, Any]]:
    unknown = sorted(set(aliases) - set(catalog))
    if unknown:
        raise ValueError(f"v27_unknown_handle_aliases:{unknown}")
    resolved = [catalog[alias] for alias in aliases]
    return resolved, {
        "status": "passed",
        "alias_count": len(aliases),
        "resolved_handles": resolved,
        "approximate_handle_repair": False,
    }


def canonicalize_unit_literal_v27(
    value: str, canonical_unit: str, frozen_aliases: dict[str, list[str]]
) -> tuple[str, dict[str, Any]]:
    """Normalize only a predeclared presentation alias and retain the source literal."""
    aliases = frozen_aliases.get(canonical_unit, [])
    if value != canonical_unit and value not in aliases:
        raise ValueError(f"v27_unit_literal_not_frozen_alias:{value}")
    return canonical_unit, {
        "status": "passed",
        "source_literal": value,
        "canonical_unit": canonical_unit,
        "alias_applied": value != canonical_unit,
        "semantic_change": False,
    }


def bind_partial_calculation_request_v27(
    model_output: dict[str, Any],
    plan: dict[str, Any],
    available_handles: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind an incomplete operation-specific request only through a frozen profile."""
    validate_candidate_handles_v26(model_output, available_handles)
    request = model_output.get("calculation_request")
    if not isinstance(request, dict):
        raise ValueError("v27_partial_calculation_request_missing")
    operation = request.get("operation")
    profile = plan.get("partial_request_profiles", {}).get(operation)
    if not isinstance(profile, list) or not profile:
        raise ValueError(f"v27_partial_calculation_profile_missing:{operation}")
    inputs = request.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != len(profile):
        raise ValueError("v27_partial_calculation_profile_arity")
    unmatched = list(inputs)
    observations: dict[str, dict[str, Any]] = {}
    for spec in profile:
        year = spec["period_year"]
        matches = [item for item in unmatched if item.get("period_year") == year]
        if len(matches) != 1:
            raise ValueError(f"v27_partial_calculation_period_ambiguous:{year}")
        item = matches[0]
        unmatched.remove(item)
        observations[spec["role_id"]] = {
            "value": item["value"],
            "period_year": item["period_year"],
            "evidence_handle": item["evidence_handle"],
            "unit": request.get("unit") or plan["candidate_input_unit"],
        }
    all_roles = [item["role_id"] for item in plan["roles"]]
    missing = [role for role in all_roles if role not in observations]
    return {"observations": observations}, {
        "status": "partially_supported",
        "operation_profile": operation,
        "bound_roles": list(observations),
        "missing_roles": missing,
        "candidate_output_complete": not missing,
        "candidate_operation_executed": False,
        "posthoc_value_invention": False,
        "approximate_handle_repair": False,
    }
