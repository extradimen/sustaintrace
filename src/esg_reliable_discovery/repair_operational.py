from __future__ import annotations

import hashlib
import json
from typing import Any

from esg_reliable_discovery.repair_execution import postvalidate, transition
from esg_reliable_discovery.v31_integrity import decode_stage_a_aliases_v31


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def execute_exact_handle_repair(
    state: dict[str, Any],
    *,
    model_output: dict[str, Any],
    alias_catalog: dict[str, str],
    expected_output: dict[str, Any],
    invariant_results: dict[str, bool],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None, str | None]:
    """Execute one isolated exact-alias repair and close success or rollback lineage."""
    if state.get("state") != "preflight_passed":
        raise ValueError("operational repair must enter with passed preflight")
    events: list[dict[str, Any]] = []
    try:
        decoded, audit = decode_stage_a_aliases_v31(model_output, alias_catalog)
    except (TypeError, ValueError) as error:
        state, event = transition(
            state,
            "failed_execution",
            checks={"registered_executor_completed": False},
        )
        events.append(event)
        state, event = transition(
            state,
            "rolled_back",
            checks={"derived_output_absent": True},
        )
        events.append(event)
        return state, events, None, f"{type(error).__name__}:{error}"

    derived = {"decode_audit": audit, "decoded_output": decoded}
    state, event = transition(
        state,
        "executed",
        checks={"registered_executor_completed": True},
    )
    events.append(event)
    actual_sha256 = hashlib.sha256(canonical_json_bytes(derived)).hexdigest()
    checks = dict(invariant_results)
    checks["output_schema_valid"] = bool(
        derived == expected_output
        and audit["approximate_handle_repair"] is False
        and audit["semantic_values_modified"] is False
    )
    state, event = postvalidate(
        state,
        actual_output_sha256=actual_sha256,
        invariant_results=checks,
    )
    events.append(event)
    if state["state"] == "postvalidation_passed":
        state, event = transition(state, "promoted", checks={"release_authorized": True})
    else:
        state, event = transition(state, "rolled_back", checks={"release_withheld": True})
    events.append(event)
    return state, events, derived, None
