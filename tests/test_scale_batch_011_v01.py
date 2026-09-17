from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]


def test_batch_eleven_sources_and_mineru_complete() -> None:
    acquisition = load_json("data/manifests/scale_batch_011_acquisition.lock.json")
    final = load_json("data/results/scale_batch_011_mineru_FINAL_summary.lock.json")
    assert acquisition["totals"]["documents"] == 3
    assert acquisition["totals"]["pages"] == 997
    assert final["complete_pages"] == 27
    assert final["failed_pages"] == 0
    assert sum(item["selected_attempt"] == "RESUME01" for item in final["records"]) == 4


def test_batch_eleven_knowledge_pipeline_fails_closed() -> None:
    increment = load_json("data/results/scale_batch_011_kb_increment.lock.json")
    repair = load_json("data/results/scale_batch_011_gap_repair.lock.json")
    projection = load_json("data/results/scale_batch_011_atomic_projection.lock.json")
    promotion = load_json("data/results/scale_batch_011_tier_b_promotion.lock.json")
    assert increment["fact_candidates"] == 32
    assert increment["evidence_gaps"] == 8
    assert repair["resolved_native_pdf_filter_gaps"] == 8
    assert projection["atomic_fact_candidates"] == 3
    assert promotion["newly_promoted_to_tier_b"] == 0
    assert len(promotion["blocked_fact_ids"]) == 3
    assert (
        len(
            load_jsonl(
                "data/knowledge_bases/v0.1/increments/scale_batch_011_semantic_failure_records.jsonl"
            )
        )
        == 1
    )


def test_batch_eleven_global_counts_and_performance() -> None:
    manifest = load_json("data/knowledge_bases/v0.1/migration_manifest.lock.json")
    performance = load_json("data/results/scale_batch_011_performance_baseline.lock.json")
    # Global stores are append-only and continue growing after Batch 11 is locked.
    assert manifest["counts"]["fact_records"] >= 1646
    assert manifest["counts"]["failure_records"] >= 299
    assert manifest["counts"]["failure_signatures"] >= 21
    assert len(load_jsonl("data/knowledge_bases/v0.1/trusted_fact_records.jsonl")) >= 79
    assert performance["whole_report_diagnostic"]["pages_per_second"] > 440
    assert performance["mineru"]["successful_target_pages_per_hour"] > 87
    assert performance["mineru"]["checkpoint_reuse_pages"] == 23
