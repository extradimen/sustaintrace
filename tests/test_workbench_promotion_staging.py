from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.workbench_promotion_staging import stage_approved_promotion


def _fact(tmp_path: Path, *, independent: bool = True) -> dict:
    first = tmp_path / "source-a.pdf"
    second = tmp_path / "source-b.pdf"
    first.write_bytes(b"source-a")
    second.write_bytes(b"source-b")
    evidence = [{
        "source_id": "source-a",
        "quote": "Water withdrawal 100 m3 in 2025.",
        "coordinates": [1, 2, 3, 4],
        "role": "issuer disclosure",
    }]
    document_ids = ["source-a"]
    metadata = [{
        "source_id": "source-a",
        "local_path": first.name,
        "sha256": hashlib.sha256(first.read_bytes()).hexdigest(),
    }]
    if independent:
        evidence.append({
            "source_id": "source-b",
            "quote": "Independently assured water withdrawal: 100 m3.",
            "coordinates": [5, 6, 7, 8],
            "role": "independent assurance",
        })
        document_ids.append("source-b")
        metadata.append({
            "source_id": "source-b",
            "local_path": second.name,
            "sha256": hashlib.sha256(second.read_bytes()).hexdigest(),
        })
    return {
        "record_id": "fact-derived",
        "knowledge_status": "reference_candidate",
        "trust_tier": "C",
        "subject": {
            "entity_label": "Example Plc",
            "document_ids": document_ids,
            "document_metadata": metadata,
        },
        "predicate": {"canonical_key": "water.withdrawal"},
        "value": 100,
        "qualifiers": {
            "reference_period": 2025,
            "normalized_unit": "m3",
            "scope_boundary": "consolidated group",
        },
        "evidence": evidence,
        "provenance": {"simulated": False},
        "promotion": {"eligible": False},
    }


def _review() -> dict:
    return {
        "review_id": "review-1",
        "version": 2,
        "state": "approved_for_promotion_staging",
        "promotion_performed": False,
    }


def test_independently_supported_candidate_is_ready_but_not_committed(tmp_path: Path) -> None:
    record = stage_approved_promotion(
        review=_review(),
        fact=_fact(tmp_path),
        trusted_facts=[],
        workspace_root=tmp_path,
    )
    schema = json.loads(
        Path("schemas/knowledge/workbench-promotion-staging-v1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(record)
    assert record["state"] == "ready_for_tier_b_overlay_commit"
    assert record["proposed_overlay"]["trust_tier"] == "B"
    assert record["proposed_overlay"]["promotion"]["committed"] is False
    assert record["promotion_performed"] is False
    assert record["trusted_layer_modified"] is False


def test_single_report_candidate_is_blocked(tmp_path: Path) -> None:
    record = stage_approved_promotion(
        review=_review(),
        fact=_fact(tmp_path, independent=False),
        trusted_facts=[],
        workspace_root=tmp_path,
    )
    assert record["state"] == "blocked_promotion_preconditions"
    assert "two_distinct_sources" in record["blocking_reasons"]
    assert "independent_or_assurance_role_present" in record["blocking_reasons"]
    assert record["proposed_overlay"] is None


def test_conflicting_trusted_fact_blocks_staging(tmp_path: Path) -> None:
    fact = _fact(tmp_path)
    trusted = {**fact, "record_id": "trusted-1", "value": 101, "trust_tier": "B"}
    record = stage_approved_promotion(
        review=_review(),
        fact=fact,
        trusted_facts=[trusted],
        workspace_root=tmp_path,
    )
    assert record["state"] == "blocked_promotion_preconditions"
    assert "controlled_conflict_clear" in record["blocking_reasons"]
    assert record["trusted_collision_record_ids"] == ["trusted-1"]


def test_equivalent_trusted_fact_is_auditable_noop(tmp_path: Path) -> None:
    fact = _fact(tmp_path)
    trusted = {**fact, "record_id": "trusted-1", "trust_tier": "B"}
    record = stage_approved_promotion(
        review=_review(),
        fact=fact,
        trusted_facts=[trusted],
        workspace_root=tmp_path,
    )
    assert record["state"] == "already_trusted_equivalent"
    assert record["proposed_overlay"] is None
    assert record["promotion_performed"] is False
