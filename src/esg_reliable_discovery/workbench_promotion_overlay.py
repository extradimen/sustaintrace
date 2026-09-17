from __future__ import annotations

from copy import deepcopy
from typing import Any

from .knowledge_base import stable_id


def active_overlay_records(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Materialize active Tier B overlays from the append-only event journal."""
    active: dict[str, dict[str, Any]] = {}
    for event in events:
        overlay_id = event.get("overlay_id")
        if not overlay_id:
            continue
        if event.get("event_type") == "overlay_committed":
            active[overlay_id] = deepcopy(event["overlay"])
        elif event.get("event_type") == "overlay_withdrawn":
            active.pop(overlay_id, None)
    return sorted(active.values(), key=lambda item: item["overlay_id"])


def commit_staged_overlay(
    *,
    staging: dict[str, Any],
    existing_events: list[dict[str, Any]],
    actor: str,
    rationale: str,
    occurred_at: str,
) -> dict[str, Any]:
    """Create an append-only commit event without mutating the base trusted layer."""
    actor = actor.strip()
    rationale = rationale.strip()
    if not actor or not rationale:
        raise ValueError("actor and rationale are required")
    if staging.get("state") != "ready_for_tier_b_overlay_commit":
        raise ValueError("staging record is not ready for Tier B overlay commit")
    proposed = staging.get("proposed_overlay")
    if not isinstance(proposed, dict):
        raise ValueError("staging record has no proposed overlay")

    overlay_id = stable_id(
        "workbench-tier-b-overlay",
        {
            "staging_id": staging["staging_id"],
            "fact_record_id": staging["fact_record_id"],
            "review_version": staging["review_version"],
        },
    )
    active = {item["overlay_id"] for item in active_overlay_records(existing_events)}
    if overlay_id in active:
        raise ValueError("Tier B overlay is already active")

    sequence = 1 + sum(
        event.get("overlay_id") == overlay_id for event in existing_events
    )
    event_id = stable_id(
        "workbench-tier-b-overlay-event",
        {"overlay_id": overlay_id, "sequence": sequence, "event_type": "commit"},
    )
    overlay = deepcopy(proposed)
    overlay.update(
        {
            "overlay_id": overlay_id,
            "trust_tier": "B",
            "knowledge_status": "trusted_overlay_active",
        }
    )
    overlay["promotion"] = {
        **overlay.get("promotion", {}),
        "eligible": True,
        "committed": True,
        "commit_event_id": event_id,
    }
    overlay["provenance"] = {
        **overlay.get("provenance", {}),
        "promotion_staging_id": staging["staging_id"],
        "promotion_review_id": staging["review_id"],
        "overlay_commit_event_id": event_id,
    }
    return {
        "schema_version": "1.0",
        "record_kind": "workbench_tier_b_overlay_event",
        "event_id": event_id,
        "event_type": "overlay_committed",
        "overlay_id": overlay_id,
        "staging_id": staging["staging_id"],
        "fact_record_id": staging["fact_record_id"],
        "actor": actor,
        "rationale": rationale,
        "occurred_at": occurred_at,
        "parent_event_id": None,
        "overlay": overlay,
        "base_trusted_layer_modified": False,
    }


def withdraw_overlay(
    *,
    overlay_id: str,
    existing_events: list[dict[str, Any]],
    actor: str,
    rationale: str,
    occurred_at: str,
) -> dict[str, Any]:
    """Withdraw an active overlay by appending a tombstone event."""
    actor = actor.strip()
    rationale = rationale.strip()
    if not actor or not rationale:
        raise ValueError("actor and rationale are required")
    active = {item["overlay_id"]: item for item in active_overlay_records(existing_events)}
    if overlay_id not in active:
        raise ValueError("Tier B overlay is not active")
    commit = next(
        event
        for event in reversed(existing_events)
        if event.get("overlay_id") == overlay_id
        and event.get("event_type") == "overlay_committed"
    )
    sequence = 1 + sum(
        event.get("overlay_id") == overlay_id for event in existing_events
    )
    event_id = stable_id(
        "workbench-tier-b-overlay-event",
        {"overlay_id": overlay_id, "sequence": sequence, "event_type": "withdraw"},
    )
    return {
        "schema_version": "1.0",
        "record_kind": "workbench_tier_b_overlay_event",
        "event_id": event_id,
        "event_type": "overlay_withdrawn",
        "overlay_id": overlay_id,
        "staging_id": commit["staging_id"],
        "fact_record_id": commit["fact_record_id"],
        "actor": actor,
        "rationale": rationale,
        "occurred_at": occurred_at,
        "parent_event_id": commit["event_id"],
        "overlay": None,
        "base_trusted_layer_modified": False,
    }
