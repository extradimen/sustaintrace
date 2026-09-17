from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import build_scale_batch_kb_increment_v01 as base
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_005_gap_repair_fact_records.jsonl"
)
FAILURE_OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_005_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_005_gap_repair.lock.json"


def markdown_at() -> Path:
    directory = ROOT / "artifacts/scale_batch_005/mineru_targets_RESUME03/KB-B005-SIKA-SR2025-p0021"
    paths = sorted(directory.rglob("*.md"))
    if len(paths) != 1:
        raise RuntimeError(f"expected_one_markdown:{directory}:{len(paths)}")
    return paths[0]


def select_biodiversity_sentence(source: Path) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", source.read_text(encoding="utf-8"))
    matches = [item.strip() for item in sentences if "biodiversity declines" in item.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"biodiversity_sentence_not_unique:{source}:{len(matches)}")
    return matches[0]


def fact_record(document: dict[str, Any], quote: str, source: Path) -> dict[str, Any]:
    identity = [document["document_id"], 21, "biodiversity", "gap-repair-01", quote]
    return {
        "schema_version": "0.1",
        "record_kind": "fact",
        "record_id": base.stable_id("fact", identity),
        "knowledge_status": "reference_candidate",
        "trust_tier": "C",
        "subject": {
            "task_id": "KB-B005-GAP-REPAIR-P0021-BIODIVERSITY",
            "entity_label": document["company"],
            "document_ids": [document["document_id"]],
            "document_metadata": [{key: document[key] for key in (
                "document_id", "company", "title", "language", "local_path", "sha256"
            )}],
        },
        "predicate": {"raw_key": "biodiversity", "canonical_key": "evidence_snippet_biodiversity"},
        "value": quote,
        "qualifiers": {
            "period_literal": "2025",
            "value_origin": "deterministic_long_paragraph_sentence_gap_repair",
            "reference_period": 2025,
            "normalized_unit": None,
            "scope_boundary": (
                "issuer climate scenario narrative, not measured biodiversity performance"
            ),
            "calculation_expression": None,
            "answer_status": "unverified_evidence_candidate",
        },
        "evidence": [{"source_id": document["document_id"], "pdf_page": 21, "quote": quote}],
        "provenance": {
            "source_artifact": source.relative_to(ROOT).as_posix(),
            "source_sha256": base.sha256_file(source),
            "reference_status": "deterministic_sentence_gap_repair_pending_semantic_projection",
            "simulated": False,
        },
        "promotion": {"eligible": False, "reason": "scenario_narrative_not_observed_metric"},
    }


def main() -> None:
    config = json.loads((ROOT / "configs/knowledge/scale_batch_005_v0.1.json").read_text())
    acquisition = json.loads(
        (ROOT / "data/manifests/scale_batch_005_acquisition.lock.json").read_text()
    )
    document = next(
        item.copy()
        for item in config["documents"]
        if item["document_id"] == "KB-B005-SIKA-SR2025"
    )
    document["sha256"] = next(
        item["sha256"]
        for item in acquisition["documents"]
        if item["document_id"] == document["document_id"]
    )
    source = markdown_at()
    facts = [fact_record(document, select_biodiversity_sentence(source), source)]
    schema = json.loads((ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text())
    for record in facts:
        Draft202012Validator(schema).validate(record)
    base.write_jsonl(OUTPUT, facts)
    base.write_jsonl(FAILURE_OUTPUT, [])
    summary = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-005-GAP-REPAIR01",
        "status": "one_long_paragraph_gap_resolved_as_candidate_not_promoted",
        "parent_gaps": 1,
        "resolved_long_paragraph_filter_gaps": 1,
        "new_fact_candidates": 1,
        "new_failure_observations": 0,
        "promoted_tier_b": 0,
        "outputs": {
            "facts": {
                "path": OUTPUT.relative_to(ROOT).as_posix(),
                "sha256": base.sha256_file(OUTPUT),
            },
            "failures": {
                "path": FAILURE_OUTPUT.relative_to(ROOT).as_posix(),
                "sha256": base.sha256_file(FAILURE_OUTPUT),
            },
        },
        "policy": {
            "parent_results_overwritten": False,
            "cloud_transmission": False,
            "automatic_promotion": False,
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
