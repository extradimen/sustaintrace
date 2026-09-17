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
    / "data/knowledge_bases/v0.1/increments/scale_batch_002_gap_repair_fact_records.jsonl"
)
FAILURE_OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_002_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_002_gap_repair.lock.json"

EON_PAGES = {
    26: ("targets", ("targets",)),
    53: (
        "energy",
        (
            "non-renewable energy consumption",
            "non-renewable energy production",
            "energy consumption intensity",
        ),
    ),
    55: (
        "water",
        (
            "water usage and recycling",
            "water consumption from powergeneration",
            "fresh water withdrawal",
            "water management policy",
            "sites located in areas of high water stress",
        ),
    ),
}


def markdown_at(directory: Path) -> Path:
    paths = sorted(directory.rglob("*.md"))
    if len(paths) != 1:
        raise RuntimeError(f"expected_one_markdown:{directory}:{len(paths)}")
    return paths[0]


def fact_record(
    *, document: dict[str, Any], page: int, theme: str, value: str, source: Path, ordinal: int,
    origin: str,
) -> dict[str, Any]:
    identity = [document["document_id"], page, theme, origin, value]
    return {
        "schema_version": "0.1",
        "record_kind": "fact",
        "record_id": base.stable_id("fact", identity),
        "knowledge_status": "reference_candidate",
        "trust_tier": "C",
        "subject": {
            "task_id": (
                f"KB-B002-GAP-REPAIR-{document['document_id']}-P{page:04d}-"
                f"{theme.upper()}-{ordinal}"
            ),
            "entity_label": document["company"],
            "document_ids": [document["document_id"]],
            "document_metadata": [
                {
                    key: document[key]
                    for key in (
                        "document_id", "company", "title", "language", "local_path"
                    )
                }
                | {"sha256": document["sha256"]},
            ],
        },
        "predicate": {
            "raw_key": theme,
            "canonical_key": f"evidence_snippet_{theme}",
        },
        "value": value,
        "qualifiers": {
            "period_literal": "2025",
            "value_origin": origin,
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


def eon_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for page, (theme, selectors) in EON_PAGES.items():
        source = markdown_at(
            ROOT
            / f"artifacts/scale_batch_002/mineru_targets/{document['document_id']}-p{page:04d}"
        )
        rows = [row for table in parse_html_tables(source.read_text()) for row in table]
        selected = []
        for selector in selectors:
            matches = [row for row in rows if selector in " | ".join(row).casefold()]
            if not matches:
                raise RuntimeError(f"repair_selector_unmatched:{page}:{selector}")
            selected.append(" | ".join(matches[0]))
        for ordinal, value in enumerate(dict.fromkeys(selected), 1):
            records.append(
                fact_record(
                    document=document,
                    page=page,
                    theme=theme,
                    value=value,
                    source=source,
                    ordinal=ordinal,
                    origin="deterministic_structured_table_row_projection",
                )
            )
    return records


def maersk_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for page in (79, 80):
        source = markdown_at(
            ROOT
            / f"artifacts/scale_batch_002/mineru_gap_repair01_RESUME01/"
            f"{document['document_id']}-p{page:04d}"
        )
        quotes = base.candidate_quotes(source.read_text(), "biodiversity")
        if not quotes:
            raise RuntimeError(f"referred_page_has_no_biodiversity_evidence:{page}")
        for ordinal, value in enumerate(quotes, 1):
            records.append(
                fact_record(
                    document=document,
                    page=page,
                    theme="biodiversity",
                    value=value,
                    source=source,
                    ordinal=ordinal,
                    origin="issuer_disclosure_extracted_from_referred_page",
                )
            )
    return records


def failure_records() -> list[dict[str, Any]]:
    parent = ROOT / "data/results/scale_batch_002_gap_repair_mineru_summary.lock.json"
    payload = json.loads(parent.read_text())
    return [
        base.failure_record(
            task_id=f"MINERU-GAP-REPAIR-{item['document_id']}-P{item['page']:04d}",
            signature="SANDBOX_LOOPBACK_PORT_DENIED",
            category="executor_or_configuration",
            diagnostic=item,
            source=parent,
        )
        for item in payload["records"]
        if item["status"] == "failed"
    ]


def main() -> None:
    acquisition = json.loads(
        (ROOT / "data/manifests/scale_batch_002_acquisition.lock.json").read_text()
    )
    config = json.loads(
        (ROOT / "configs/knowledge/scale_batch_002_v0.1.json").read_text()
    )
    documents = {item["document_id"]: item for item in config["documents"]}
    for item in acquisition["documents"]:
        documents[item["document_id"]]["sha256"] = item["sha256"]
    facts = eon_records(documents["KB-B002-EON-SF2025"])
    facts.extend(maersk_records(documents["KB-B002-MAERSK-AR2025"]))
    failures = failure_records()
    fact_schema = json.loads(
        (ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text()
    )
    failure_schema = json.loads(
        (ROOT / "schemas/knowledge/failure-record-v0.1.schema.json").read_text()
    )
    for record in facts:
        Draft202012Validator(fact_schema).validate(record)
    for record in failures:
        Draft202012Validator(failure_schema).validate(record)
    base.write_jsonl(OUTPUT, facts)
    base.write_jsonl(FAILURE_OUTPUT, failures)
    summary = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-002-GAP-REPAIR01",
        "status": "four_gaps_resolved_as_candidates_not_promoted",
        "parent_gaps": 4,
        "resolved_structured_table_filter_gaps": 3,
        "resolved_index_to_disclosure_page_gaps": 1,
        "new_fact_candidates": len(facts),
        "new_failure_observations": len(failures),
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
