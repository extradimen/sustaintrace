from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.workbench_promotion_overlay import (
    active_overlay_records,
    commit_staged_overlay,
    withdraw_overlay,
)


def _staging() -> dict:
    return {
        "staging_id": "workbench-promotion-staging-1",
        "review_id": "review-1",
        "review_version": 2,
        "fact_record_id": "fact-1",
        "state": "ready_for_tier_b_overlay_commit",
        "proposed_overlay": {
            "record_id": "fact-1",
            "trust_tier": "B",
            "promotion": {"eligible": True, "committed": False},
        },
    }


def test_commit_materializes_overlay_without_mutating_staging() -> None:
    staging = _staging()
    event = commit_staged_overlay(
        staging=staging,
        existing_events=[],
        actor="reviewer",
        rationale="Independent evidence verified.",
        occurred_at="2026-09-17T00:00:00Z",
    )
    active = active_overlay_records([event])
    schema = json.loads(
        Path("schemas/knowledge/workbench-tier-b-overlay-event-v1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(event)
    assert len(active) == 1
    assert active[0]["trust_tier"] == "B"
    assert active[0]["promotion"]["committed"] is True
    assert event["base_trusted_layer_modified"] is False
    assert staging["proposed_overlay"]["promotion"]["committed"] is False


def test_withdrawal_removes_active_view_but_preserves_journal() -> None:
    commit = commit_staged_overlay(
        staging=_staging(),
        existing_events=[],
        actor="reviewer",
        rationale="Independent evidence verified.",
        occurred_at="2026-09-17T00:00:00Z",
    )
    withdrawal = withdraw_overlay(
        overlay_id=commit["overlay_id"],
        existing_events=[commit],
        actor="reviewer",
        rationale="Source was superseded.",
        occurred_at="2026-09-17T01:00:00Z",
    )
    assert active_overlay_records([commit, withdrawal]) == []
    schema = json.loads(
        Path("schemas/knowledge/workbench-tier-b-overlay-event-v1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(withdrawal)
    assert withdrawal["parent_event_id"] == commit["event_id"]
    assert withdrawal["base_trusted_layer_modified"] is False


def test_duplicate_active_commit_and_double_withdrawal_are_rejected() -> None:
    commit = commit_staged_overlay(
        staging=_staging(),
        existing_events=[],
        actor="reviewer",
        rationale="Independent evidence verified.",
        occurred_at="2026-09-17T00:00:00Z",
    )
    try:
        commit_staged_overlay(
            staging=_staging(),
            existing_events=[commit],
            actor="reviewer",
            rationale="Duplicate.",
            occurred_at="2026-09-17T00:01:00Z",
        )
    except ValueError as exc:
        assert "already active" in str(exc)
    else:
        raise AssertionError("duplicate commit must fail closed")

    withdrawal = withdraw_overlay(
        overlay_id=commit["overlay_id"],
        existing_events=[commit],
        actor="reviewer",
        rationale="Withdraw.",
        occurred_at="2026-09-17T01:00:00Z",
    )
    try:
        withdraw_overlay(
            overlay_id=commit["overlay_id"],
            existing_events=[commit, withdrawal],
            actor="reviewer",
            rationale="Withdraw twice.",
            occurred_at="2026-09-17T01:01:00Z",
        )
    except ValueError as exc:
        assert "not active" in str(exc)
    else:
        raise AssertionError("double withdrawal must fail closed")
