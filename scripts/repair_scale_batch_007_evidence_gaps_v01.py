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
    / "data/knowledge_bases/v0.1/increments/scale_batch_007_gap_repair_fact_records.jsonl"
)
FAILURE_OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_007_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_007_gap_repair.lock.json"


def table_cells(markdown: str) -> list[str]:
    cells = []
    for raw in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", markdown, flags=re.I | re.S):
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        normalized = " ".join(text.split())
        if normalized:
            cells.append(normalized)
    return cells


def select_cell(markdown: str, theme: str) -> str:
    terms = base.THEME_TERMS[theme]
    usable = [
        cell
        for cell in table_cells(markdown)
        if 25 <= len(cell) <= 800 and any(term in cell.casefold() for term in terms)
    ]
    numeric = [cell for cell in usable if re.search(r"\d", cell)]
    selected = numeric[:1] or usable[:1]
    if len(selected) != 1:
        raise RuntimeError(f"no_deterministic_table_cell:{theme}")
    return selected[0]


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
                f"KB-B007-GAP-REPAIR-{document['document_id']}-"
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
            "value_origin": "deterministic_html_table_cell_gap_repair",
            "reference_period": 2025,
            "normalized_unit": None,
            "scope_boundary": None,
            "calculation_expression": None,
            "answer_status": "unverified_evidence_candidate",
        },
        "evidence": [
            {
                "source_id": document["document_id"],
                "pdf_page": gap["page"],
                "quote": quote,
            }
        ],
        "provenance": {
            "source_artifact": source.relative_to(ROOT).as_posix(),
            "source_sha256": base.sha256_file(source),
            "reference_status": (
                "deterministic_html_table_cell_gap_repair_pending_semantic_projection"
            ),
            "simulated": False,
        },
        "promotion": {
            "eligible": False,
            "reason": "requires_semantic_projection_and_independent_evidence_gate",
        },
    }


def main() -> None:
    config = base.read_json(ROOT / "configs/knowledge/scale_batch_007_v0.1.json")
    acquisition = base.read_json(
        ROOT / "data/manifests/scale_batch_007_acquisition.lock.json"
    )
    final = base.read_json(
        ROOT / "data/results/scale_batch_007_mineru_FINAL_summary.lock.json"
    )
    gaps = base.read_json(ROOT / "data/results/scale_batch_007_kb_increment.lock.json")[
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
        quote = select_cell(
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
        "batch_id": "KB-SCALE-BATCH-007-GAP-REPAIR01",
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
