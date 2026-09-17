from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import build_scale_batch_kb_increment_v01 as base
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_009_gap_repair_fact_records.jsonl"
)
FAILURE_OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_009_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_009_gap_repair.lock.json"


def table_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_row in re.findall(r"<tr[^>]*>(.*?)</tr>", markdown, flags=re.I | re.S):
        cells = []
        for raw_cell in re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>", raw_row, flags=re.I | re.S
        ):
            text = html.unescape(re.sub(r"<[^>]+>", " ", raw_cell))
            normalized = " ".join(text.split())
            cells.append(normalized)
        if any(cells):
            rows.append(cells)
    return rows


def select_row(markdown: str, theme: str) -> str:
    rows = table_rows(markdown)
    anchors = [
        index
        for index, row in enumerate(rows)
        if row and row[0].casefold() == theme.casefold()
    ]
    if len(anchors) != 1:
        raise RuntimeError(f"non_unique_deterministic_table_row:{theme}:{len(anchors)}")
    start = anchors[0]
    selected = [rows[start]]
    for row in rows[start + 1 :]:
        if row[0]:
            break
        selected.append(row)
    quote = " || ".join(" | ".join(cell for cell in row if cell) for row in selected)
    if not 25 <= len(quote) <= 2000:
        raise RuntimeError(f"invalid_deterministic_table_row_length:{theme}:{len(quote)}")
    return quote


def fact_record(
    document: dict[str, Any], gap: dict[str, Any], quote: str, source: Path
) -> dict[str, Any]:
    identity = [document["document_id"], gap["page"], gap["theme"], "gap-repair-01", quote]
    return {
        "schema_version": "0.1",
        "record_kind": "fact",
        "record_id": base.stable_id("fact", identity),
        "knowledge_status": "reference_candidate",
        "trust_tier": "C",
        "subject": {
            "task_id": (
                f"KB-B009-GAP-REPAIR-{document['document_id']}-"
                f"P{gap['page']:04d}-{gap['theme'].upper()}"
            ),
            "entity_label": document["company"],
            "document_ids": [document["document_id"]],
            "document_metadata": [
                {
                    key: document[key]
                    for key in (
                        "document_id",
                        "company",
                        "title",
                        "language",
                        "local_path",
                        "sha256",
                    )
                }
            ],
        },
        "predicate": {
            "raw_key": gap["theme"],
            "canonical_key": f"evidence_snippet_{gap['theme']}",
        },
        "value": quote,
        "qualifiers": {
            "period_literal": "2025",
            "value_origin": "deterministic_html_table_row_gap_repair",
            "reference_period": 2025,
            "normalized_unit": None,
            "scope_boundary": None,
            "calculation_expression": None,
            "answer_status": "unverified_evidence_candidate",
        },
        "evidence": [
            {"source_id": document["document_id"], "pdf_page": gap["page"], "quote": quote}
        ],
        "provenance": {
            "source_artifact": source.relative_to(ROOT).as_posix(),
            "source_sha256": base.sha256_file(source),
            "reference_status": (
                "deterministic_html_table_row_gap_repair_pending_semantic_projection"
            ),
            "simulated": False,
        },
        "promotion": {
            "eligible": False,
            "reason": "requires_semantic_projection_and_independent_evidence_gate",
        },
    }


def main() -> None:
    config = base.read_json(ROOT / "configs/knowledge/scale_batch_009_v0.1.json")
    acquisition = base.read_json(
        ROOT / "data/manifests/scale_batch_009_acquisition.lock.json"
    )
    final = base.read_json(
        ROOT / "data/results/scale_batch_009_mineru_FINAL_summary.lock.json"
    )
    gaps = base.read_json(ROOT / "data/results/scale_batch_009_kb_increment.lock.json")[
        "gaps"
    ]
    documents = {item["document_id"]: item.copy() for item in config["documents"]}
    for item in acquisition["documents"]:
        documents[item["document_id"]]["sha256"] = item["sha256"]
    outputs = {
        (item["document_id"], item["page"]): next(
            (ROOT / item["output_directory"]).rglob("*.md")
        )
        for item in final["records"]
    }
    facts = []
    for gap in gaps:
        source = outputs[(gap["document_id"], gap["page"])]
        quote = select_row(
            source.read_text(encoding="utf-8", errors="replace"), gap["theme"]
        )
        facts.append(fact_record(documents[gap["document_id"]], gap, quote, source))
    schema = base.read_json(ROOT / "schemas/knowledge/fact-record-v0.1.schema.json")
    for record in facts:
        Draft202012Validator(schema).validate(record)
    base.write_jsonl(OUTPUT, facts)
    base.write_jsonl(FAILURE_OUTPUT, [])
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-009-GAP-REPAIR01",
        "status": "all_html_table_line_filter_gaps_resolved_as_candidates_not_promoted",
        "parent_gaps": len(gaps),
        "resolved_html_table_filter_gaps": len(facts),
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
    SUMMARY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
