from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import build_scale_batch_kb_increment_v01 as base
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_011_gap_repair_fact_records.jsonl"
FAILURE_OUTPUT = (
    ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_011_gap_repair_failure_records.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_011_gap_repair.lock.json"

# The anchors and bounded line windows are frozen here so the native-PDF fallback is
# reproducible.  They recover evidence missed by the generic MinerU line filter; they
# do not promote any record or reinterpret a locked experiment.
SPECS = {
    ("KB-B011-ENI-SS2025", 8, "assurance"): (
        "subject to a limited assurance",
        2,
        0,
    ),
    ("KB-B011-ENI-SS2025", 33, "ghg_emissions"): (
        "CO2 Scope 1 emissions are reported separately",
        1,
        1,
    ),
    ("KB-B011-DSMF-SS2025", 3, "assurance"): (
        "subjected to limited assurance. A number of",
        0,
        1,
    ),
    ("KB-B011-DSMF-SS2025", 30, "targets"): (
        "2021",
        0,
        20,
    ),
    ("KB-B011-DSMF-SS2025", 89, "workforce"): (
        "S1-6          Characteristics of the undertaking’s employees",
        0,
        1,
    ),
    ("KB-B011-DB-AR2025", 341, "water"): (
        "wildfire, drought, and water stress",
        2,
        4,
    ),
    ("KB-B011-DB-AR2025", 427, "workforce"): (
        "Stakeholder engagement and thought leadership – Employees",
        0,
        2,
    ),
    ("KB-B011-DB-AR2025", 435, "health_safety"): (
        "Number of fatalities and",
        1,
        4,
    ),
}


def native_page(source: Path, page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(source), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def select_window(text: str, anchor: str, before: int, after: int) -> str:
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if anchor in line]
    if len(matches) != 1:
        raise RuntimeError(f"native_anchor_not_unique:{anchor}:{len(matches)}")
    index = matches[0]
    selected = lines[max(0, index - before) : min(len(lines), index + after + 1)]
    quote = " ".join(" ".join(line.split()) for line in selected if line.strip())
    if not 25 <= len(quote) <= 2000:
        raise RuntimeError(f"invalid_native_window_length:{anchor}:{len(quote)}")
    return quote


def fact_record(
    document: dict[str, Any], page: int, theme: str, quote: str, source: Path
) -> dict[str, Any]:
    identity = [document["document_id"], page, theme, "native-gap-repair-01", quote]
    return {
        "schema_version": "0.1",
        "record_kind": "fact",
        "record_id": base.stable_id("fact", identity),
        "knowledge_status": "reference_candidate",
        "trust_tier": "C",
        "subject": {
            "task_id": (
                f"KB-B011-GAP-REPAIR-{document['document_id']}-P{page:04d}-{theme.upper()}"
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
            "raw_key": theme,
            "canonical_key": f"evidence_snippet_{theme}",
        },
        "value": quote,
        "qualifiers": {
            "period_literal": "2025",
            "value_origin": "deterministic_native_pdf_layout_gap_repair",
            "reference_period": 2025,
            "normalized_unit": None,
            "scope_boundary": None,
            "calculation_expression": None,
            "answer_status": "unverified_evidence_candidate",
        },
        "evidence": [{"source_id": document["document_id"], "pdf_page": page, "quote": quote}],
        "provenance": {
            "source_artifact": source.relative_to(ROOT).as_posix(),
            "source_sha256": base.sha256_file(source),
            "reference_status": ("deterministic_native_pdf_gap_repair_pending_semantic_projection"),
            "simulated": False,
        },
        "promotion": {
            "eligible": False,
            "reason": "requires_semantic_projection_and_independent_evidence_gate",
        },
    }


def main() -> None:
    config = base.read_json(ROOT / "configs/knowledge/scale_batch_011_RESUME01_v0.2.json")
    acquisition = base.read_json(ROOT / "data/manifests/scale_batch_011_acquisition.lock.json")
    gaps = base.read_json(ROOT / "data/results/scale_batch_011_kb_increment.lock.json")["gaps"]
    documents = {item["document_id"]: item.copy() for item in config["documents"]}
    for item in acquisition["documents"]:
        documents[item["document_id"]]["sha256"] = item["sha256"]
    observed = {(item["document_id"], item["page"], item["theme"]) for item in gaps}
    if observed != set(SPECS):
        raise RuntimeError("fail-closed: batch-eleven gap inventory changed")

    facts = []
    native_hashes = {}
    for key, (anchor, before, after) in SPECS.items():
        document_id, page, theme = key
        document = documents[document_id]
        source = ROOT / document["local_path"]
        text = native_page(source, page)
        quote = select_window(text, anchor, before, after)
        facts.append(fact_record(document, page, theme, quote, source))
        native_hashes[f"{document_id}:p{page}"] = hashlib.sha256(text.encode()).hexdigest()

    schema = base.read_json(ROOT / "schemas/knowledge/fact-record-v0.1.schema.json")
    for record in facts:
        Draft202012Validator(schema).validate(record)
    base.write_jsonl(OUTPUT, facts)
    base.write_jsonl(FAILURE_OUTPUT, [])
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-011-GAP-REPAIR01",
        "status": "all_native_pdf_line_filter_gaps_resolved_as_candidates_not_promoted",
        "parent_gaps": len(gaps),
        "resolved_native_pdf_filter_gaps": len(facts),
        "new_fact_candidates": len(facts),
        "new_failure_observations": 0,
        "promoted_tier_b": 0,
        "native_page_text_sha256": native_hashes,
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
    SUMMARY.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
