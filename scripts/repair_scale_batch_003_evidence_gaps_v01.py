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
    / "data/knowledge_bases/v0.1/increments/scale_batch_003_gap_repair_fact_records.jsonl"
)
FAILURE_OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_003_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_003_gap_repair.lock.json"


def markdown_at(directory: Path) -> Path:
    paths = sorted(directory.rglob("*.md"))
    if len(paths) != 1:
        raise RuntimeError(f"expected_one_markdown:{directory}:{len(paths)}")
    return paths[0]


def source_for(document_id: str, page: int) -> Path:
    root = "mineru_targets_RESUME01" if (document_id, page) == (
        "KB-B003-DHL-AR2025",
        127,
    ) else "mineru_targets"
    return markdown_at(
        ROOT / f"artifacts/scale_batch_003/{root}/{document_id}-p{page:04d}"
    )


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
            "task_id": (
                f"KB-B003-GAP-REPAIR-{document['document_id']}-P{page:04d}-"
                f"{theme.upper()}"
            ),
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
            "value_origin": "deterministic_gap_repair_projection",
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


SELECTORS = (
    ("KB-B003-INGKA-ASSR-FY25", 70, "ghg_emissions", "Total scope 1 & 2"),
    ("KB-B003-AZ-SDA2025", 3, "targets", "Reduce absolute Scope 1 and 2"),
    ("KB-B003-AZ-SDA2025", 4, "energy", "Total energy consumption from sites"),
    ("KB-B003-AZ-SDA2025", 5, "circularity", "Waste management Total waste"),
    ("KB-B003-AZ-SDA2025", 5, "water", "Water withdrawal within site water footprint"),
    ("KB-B003-AZ-SDA2025", 10, "health_safety", "Total reportable injury rate"),
    ("KB-B003-AZ-SDA2025", 10, "workforce", "Employee turnover"),
    ("KB-B003-DHL-AR2025", 125, "workforce", "Characteristics of the undertaking's employees"),
    ("KB-B003-DHL-AR2025", 127, "water", "ESRS E3-4 Total water recycled"),
)


def selected_table_row(source: Path, selector: str) -> str:
    rows = [row for table in parse_html_tables(source.read_text()) for row in table]
    matches = [" | ".join(row) for row in rows if selector.casefold() in " | ".join(row).casefold()]
    if not matches:
        raise RuntimeError(f"repair_selector_unmatched:{source}:{selector}")
    return matches[0]


def biodiversity_paragraph(source: Path) -> str:
    paragraphs = [item.strip() for item in source.read_text().split("\n\n") if item.strip()]
    matches = [item for item in paragraphs if item.startswith("Biodiversity (ESRS E4):")]
    if len(matches) != 1:
        raise RuntimeError(f"biodiversity_paragraph_not_unique:{source}:{len(matches)}")
    return matches[0]


def main() -> None:
    config = json.loads((ROOT / "configs/knowledge/scale_batch_003_v0.1.json").read_text())
    acquisition = json.loads(
        (ROOT / "data/manifests/scale_batch_003_acquisition_FINAL.lock.json").read_text()
    )
    documents = {item["document_id"]: item for item in config["documents"]}
    for item in acquisition["documents"]:
        documents[item["document_id"]]["sha256"] = item["sha256"]

    facts = []
    for document_id, page, theme, selector in SELECTORS:
        source = source_for(document_id, page)
        facts.append(
            fact_record(
                document=documents[document_id],
                page=page,
                theme=theme,
                value=selected_table_row(source, selector),
                source=source,
            )
        )
    source = source_for("KB-B003-DHL-AR2025", 76)
    facts.append(
        fact_record(
            document=documents["KB-B003-DHL-AR2025"],
            page=76,
            theme="biodiversity",
            value=biodiversity_paragraph(source),
            source=source,
        )
    )

    fact_schema = json.loads(
        (ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text()
    )
    for record in facts:
        Draft202012Validator(fact_schema).validate(record)
    base.write_jsonl(OUTPUT, facts)
    base.write_jsonl(FAILURE_OUTPUT, [])
    summary = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-003-GAP-REPAIR01",
        "status": "ten_gaps_resolved_as_candidates_not_promoted",
        "parent_gaps": 10,
        "resolved_structured_table_filter_gaps": 9,
        "resolved_long_paragraph_filter_gaps": 1,
        "new_fact_candidates": len(facts),
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
