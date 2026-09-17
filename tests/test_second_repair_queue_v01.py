import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_queue import (
    REPAIR_LANES,
    build_second_repair_queue,
    summarize_second_repair_queue,
)

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    gaps = [
        {
            "gap_id": f"gap-{index:024x}",
            "fact_record_id": f"fact-{index:024x}",
            "task_id": f"TASK-{index}",
            "gap_signature": signature,
            "current_state": "incomplete",
            "required_state": "complete",
        }
        for index, signature in enumerate(REPAIR_LANES, start=1)
    ]
    rankings = [
        {"gap_signature": signature, "risk": risk, "rank": index}
        for index, (signature, risk) in enumerate(
            [
                ("PERIOD_ATTACHMENT_INCOMPLETE", "low"),
                ("BOUNDARY_ATTACHMENT_INCOMPLETE", "high"),
                ("NATIVE_PDF_CORROBORATION_INCOMPLETE", "medium"),
                ("TABLE_CELL_BINDING_INCOMPLETE", "medium"),
                ("FIELD_EVIDENCE_BINDING_INCOMPLETE", "medium"),
                ("UNIT_ATTACHMENT_INCOMPLETE", "medium"),
                ("CALCULATION_LINEAGE_INCOMPLETE", "medium"),
            ],
            start=1,
        )
    ]
    return gaps, rankings


def build():
    gaps, rankings = fixtures()
    return build_second_repair_queue(
        gaps=gaps,
        rankings=rankings,
        gaps_sha256="a" * 64,
        rankings_sha256="b" * 64,
    )


def test_all_gap_signatures_route_once_with_stable_unique_ids():
    first = build()
    second = build()
    assert first == second
    assert len(first) == len(REPAIR_LANES)
    assert len({item["queue_id"] for item in first}) == len(first)


def test_boundary_is_blocked_and_no_queue_item_executes_or_repairs_semantics():
    records = build()
    boundary = next(
        item for item in records if item["gap_signature"] == "BOUNDARY_ATTACHMENT_INCOMPLETE"
    )
    assert boundary["execution_decision"] == "blocked"
    assert boundary["queue_class"] == "semantic_block"
    assert all(item["execution_performed"] is False for item in records)
    assert all(item["semantic_repair_allowed"] is False for item in records)


def test_period_and_unit_only_enter_deterministic_screens():
    records = build()
    screened = {
        item["gap_signature"]
        for item in records
        if item["queue_class"] == "deterministic_binding_screen"
    }
    assert screened == {"PERIOD_ATTACHMENT_INCOMPLETE", "UNIT_ATTACHMENT_INCOMPLETE"}


def test_summary_counts_every_queue_item():
    summary = summarize_second_repair_queue(build())
    assert summary["records"] == len(REPAIR_LANES)
    assert sum(summary["queue_class_counts"].values()) == summary["records"]


def test_unknown_signature_fails_closed():
    gaps, rankings = fixtures()
    gaps[0]["gap_signature"] = "UNKNOWN"
    with pytest.raises(ValueError, match="unroutable_knowledge_gap"):
        build_second_repair_queue(
            gaps=gaps,
            rankings=rankings,
            gaps_sha256="a" * 64,
            rankings_sha256="b" * 64,
        )


def test_queue_items_validate_against_frozen_schema():
    schema = json.loads(
        (ROOT / "schemas/knowledge/second-repair-queue-item-v0.1.schema.json").read_text()
    )
    validator = Draft202012Validator(schema)
    for record in build():
        validator.validate(record)


def test_frozen_queue_is_complete_schema_valid_and_hash_locked():
    queue_path = ROOT / "data/knowledge_bases/v0.1/second_repair_queue.jsonl"
    summary = json.loads(
        (ROOT / "data/knowledge_bases/v0.1/second_repair_queue_summary.lock.json").read_text()
    )
    schema = json.loads(
        (ROOT / "schemas/knowledge/second-repair-queue-item-v0.1.schema.json").read_text()
    )
    validator = Draft202012Validator(schema)
    records = [json.loads(line) for line in queue_path.read_text().splitlines() if line]
    for record in records:
        validator.validate(record)
    assert len(records) == summary["records"] == 2660
    assert len({record["queue_id"] for record in records}) == len(records)
    assert sha256_file(queue_path) == summary["output"]["sha256"]
