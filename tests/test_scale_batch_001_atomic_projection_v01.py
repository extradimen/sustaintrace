from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_atomic_fact_records.jsonl"
VALIDATIONS = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_001_atomic_validation.lock.json"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_atomic_projection_preserves_coordinates_and_stays_candidate() -> None:
    records = load_jsonl(FACTS)
    assert records
    assert all(record["trust_tier"] == "C" for record in records)
    assert all(record["promotion"]["eligible"] is False for record in records)
    for record in records:
        evidence = record["evidence"][0]
        assert evidence["row_index"] >= 1
        assert evidence["column_index"] >= 1
        assert evidence["row_header"]
        assert evidence["column_header"]
        assert evidence["cell_handle"].startswith("cell-")


def test_danone_2025_water_value_is_bound_to_correct_axes() -> None:
    records = load_jsonl(FACTS)
    target = next(
        record
        for record in records
        if record["predicate"]["canonical_key"] == "water_related_to_the_production_process"
        and record["qualifiers"]["period_literal"] == "2025"
    )
    assert target["value"] == "33184"
    assert target["qualifiers"]["normalized_unit"] == "thousand_m3"
    assert target["evidence"][0]["quote"] == "33,184"


def test_atomic_validation_is_fail_closed() -> None:
    records = load_jsonl(VALIDATIONS)
    summary = json.loads(SUMMARY.read_text())
    assert len(records) == 14
    assert all(record["promotion_decision"] == "hold_tier_c" for record in records)
    assert all(
        record["independent_assurance_cell_scope_verified"] is False
        for record in records
    )
    assert summary["candidate_count"] == 14
    assert summary["promoted_tier_b_count"] == 0
