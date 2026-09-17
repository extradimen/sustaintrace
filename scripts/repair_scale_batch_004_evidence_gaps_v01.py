from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_scale_batch_kb_increment_v01 as base
from jsonschema import Draft202012Validator

from esg_reliable_discovery.table_projection import parse_html_tables

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_004_gap_repair_fact_records.jsonl"
)
FAILURE_OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_004_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_004_gap_repair.lock.json"


def markdown_at(page: int) -> Path:
    directory = (
        ROOT
        / "artifacts/scale_batch_004/mineru_targets_RESUME01"
        / f"KB-B004-PHILIPS-AR2025-p{page:04d}"
    )
    paths = sorted(directory.rglob("*.md"))
    if len(paths) != 1:
        raise RuntimeError(f"expected_one_markdown:{directory}:{len(paths)}")
    return paths[0]


def select_row(source: Path, selector: str) -> str:
    rows = [row for table in parse_html_tables(source.read_text()) for row in table]
    matches = [" | ".join(row) for row in rows if selector.casefold() in " | ".join(row).casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"repair_selector_not_unique:{source}:{selector}:{len(matches)}")
    return matches[0]


def fact_record(
    *, document: dict[str, Any], page: int, theme: str, value: str, source: Path
) -> dict[str, Any]:
    identity = [document["document_id"], page, theme, "gap-repair-01", value]
    return {
        "schema_version": "0.1",
        "record_kind": "fact",
        "record_id": base.stable_id("fact", identity),
        "knowledge_status": "reference_candidate",
        "trust_tier": "C",
        "subject": {
            "task_id": f"KB-B004-GAP-REPAIR-P{page:04d}-{theme.upper()}",
            "entity_label": document["company"],
            "document_ids": [document["document_id"]],
            "document_metadata": [
                {
                    key: document[key]
                    for key in ("document_id", "company", "title", "language", "local_path")
                }
                | {"sha256": document["sha256"]}
            ],
        },
        "predicate": {"raw_key": theme, "canonical_key": f"evidence_snippet_{theme}"},
        "value": value,
        "qualifiers": {
            "period_literal": "2025",
            "value_origin": "deterministic_structured_table_gap_repair",
            "reference_period": 2025,
            "normalized_unit": None,
            "scope_boundary": None,
            "calculation_expression": None,
            "answer_status": "unverified_evidence_candidate",
        },
        "evidence": [
            {"source_id": document["document_id"], "pdf_page": page, "quote": value}
        ],
        "provenance": {
            "source_artifact": source.relative_to(ROOT).as_posix(),
            "source_sha256": base.sha256_file(source),
            "reference_status": "deterministic_gap_repair_pending_semantic_projection",
            "simulated": False,
        },
        "promotion": {
            "eligible": False,
            "reason": "requires_atomic_projection_and_independent_evidence_gate",
        },
    }


def main() -> None:
    config = json.loads(
        (ROOT / "configs/knowledge/scale_batch_004_RESUME01_v0.2.json").read_text()
    )
    acquisition = json.loads(
        (ROOT / "data/manifests/scale_batch_004_acquisition_FINAL.lock.json").read_text()
    )
    document = next(
        item for item in config["documents"] if item["document_id"] == "KB-B004-PHILIPS-AR2025"
    )
    document["sha256"] = next(
        item["sha256"]
        for item in acquisition["documents"]
        if item["document_id"] == document["document_id"]
    )
    selectors = (
        (244, "circularity", "Disclosure Requirement E5-3"),
        (245, "assurance", "Disclosure Requirement S1-6"),
    )
    facts = []
    for page, theme, selector in selectors:
        source = markdown_at(page)
        facts.append(
            fact_record(
                document=document,
                page=page,
                theme=theme,
                value=select_row(source, selector),
                source=source,
            )
        )
    schema = json.loads((ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text())
    for record in facts:
        Draft202012Validator(schema).validate(record)
    base.write_jsonl(OUTPUT, facts)
    base.write_jsonl(FAILURE_OUTPUT, [])
    summary = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-004-GAP-REPAIR01",
        "status": "two_gaps_resolved_as_candidates_not_promoted",
        "parent_gaps": 2,
        "resolved_structured_table_filter_gaps": 2,
        "new_fact_candidates": 2,
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
