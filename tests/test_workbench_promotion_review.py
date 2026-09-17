from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from esg_reliable_discovery.workbench_promotion_review import (
    build_promotion_review_queue,
    decide_promotion_review,
)


def _queue() -> list[dict]:
    fact = {"record_id": "fact-derived", "trust_tier": "C"}
    execution = {
        "execution_id": "execution-1",
        "parent_fact_record_id": "fact-parent",
        "derived_fact_record_id": "fact-derived",
        "state": "postvalidation_passed",
        "checks": {"unique_cell": True, "source_hash": True},
        "promotion_performed": False,
        "trusted_layer_modified": False,
        "cloud_transfer_performed": False,
    }
    return build_promotion_review_queue(
        repaired_facts=[fact],
        repair_executions=[execution],
    )


def test_queue_is_schema_valid_and_fail_closed() -> None:
    records = _queue()
    schema = json.loads(
        Path("schemas/knowledge/workbench-promotion-review-v1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(records[0])
    assert records[0]["state"] == "pending_review"
    assert records[0]["promotion_performed"] is False
    assert records[0]["trusted_layer_modified"] is False


def test_approval_only_stages_promotion_and_preserves_candidate() -> None:
    record = _queue()[0]
    approved = decide_promotion_review(
        record,
        decision="approve_for_promotion_staging",
        reviewer="local reviewer",
        rationale="The evidence and deterministic binding are complete.",
        expected_version=1,
    )
    assert approved["state"] == "approved_for_promotion_staging"
    assert approved["version"] == 2
    assert approved["promotion_performed"] is False
    assert approved["trusted_layer_modified"] is False
    assert record["state"] == "pending_review"


def test_review_rejects_stale_version_and_second_decision() -> None:
    record = _queue()[0]
    with pytest.raises(ValueError, match="version conflict"):
        decide_promotion_review(
            record,
            decision="reject",
            reviewer="reviewer",
            rationale="Evidence is insufficient.",
            expected_version=2,
        )
    rejected = decide_promotion_review(
        record,
        decision="reject",
        reviewer="reviewer",
        rationale="Evidence is insufficient.",
        expected_version=1,
    )
    with pytest.raises(ValueError, match="no longer pending"):
        decide_promotion_review(
            rejected,
            decision="approve_for_promotion_staging",
            reviewer="reviewer",
            rationale="Changed mind.",
            expected_version=2,
        )
