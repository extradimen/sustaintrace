from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_jsonl(path: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_batch_acquisition_and_parser_coverage() -> None:
    acquisition = load("data/manifests/scale_batch_001_acquisition.lock.json")
    diagnostics = load("data/results/scale_batch_001_diagnostics.lock.json")
    target = load("data/manifests/scale_batch_001_target_pages.lock.json")
    resume1 = load("data/results/scale_batch_001_mineru_RESUME01_summary.lock.json")
    resume2 = load("data/results/scale_batch_001_mineru_RESUME02_summary.lock.json")
    assert len(acquisition["documents"]) == 3
    assert diagnostics["totals"] == {"documents": 3, "pdf_pages": 786, "extractable_pages": 785}
    assert target["totals"]["unique_target_pages"] == 26
    assert resume1["complete_pages"] == 25
    assert resume1["failed_pages"] == 1
    assert resume2["complete_pages"] == 1
    assert resume2["failed_pages"] == 0


def test_batch_increment_is_valid_and_not_promoted() -> None:
    facts = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_001_fact_records.jsonl"
    )
    failures = load_jsonl(
        "data/knowledge_bases/v0.1/increments/scale_batch_001_failure_records.jsonl"
    )
    fact_schema = load("schemas/knowledge/fact-record-v0.1.schema.json")
    failure_schema = load("schemas/knowledge/failure-record-v0.1.schema.json")
    assert len(facts) == 41
    assert len(failures) == 30
    assert all(item["trust_tier"] == "C" for item in facts)
    assert all(item["promotion"]["eligible"] is False for item in facts)
    for record in facts:
        Draft202012Validator(fact_schema).validate(record)
    for record in failures:
        Draft202012Validator(failure_schema).validate(record)


def test_evidence_gate_and_global_inventory() -> None:
    gate = load("data/results/scale_batch_001_evidence_gate.lock.json")
    audit = load("data/results/scale_batch_001_final_audit.lock.json")
    facts = load_jsonl("data/knowledge_bases/v0.1/fact_records.jsonl")
    failures = load_jsonl("data/knowledge_bases/v0.1/failure_records.jsonl")
    assert gate["candidate_count"] == 41
    assert gate["mineru_exact_count"] == 41
    assert gate["held_tier_c_count"] == 41
    assert gate["promoted_tier_b_count"] == 0
    assert audit["checks"]["all_target_pages_have_successful_generation"] is True
    assert len(facts) >= 1076
    assert len(failures) >= 66
