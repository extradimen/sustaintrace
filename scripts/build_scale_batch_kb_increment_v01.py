from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from esg_reliable_discovery.mineru_text_fallback import (
    read_mineru_text_source,
    select_mineru_text_source,
)

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "data/manifests/scale_batch_001_target_pages.lock.json"
SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_001_RESUME01_v0.2.json"
FAILURES = ROOT / "data/manifests/scale_batch_001_acquisition_failures.lock.json"
INITIAL = ROOT / "data/results/scale_batch_001_mineru_summary.lock.json"
RESUME01 = ROOT / "data/results/scale_batch_001_mineru_RESUME01_summary.lock.json"
RESUME02 = ROOT / "data/results/scale_batch_001_mineru_RESUME02_summary.lock.json"
INCREMENT_DIR = ROOT / "data/knowledge_bases/v0.1/increments"
FACT_OUTPUT = INCREMENT_DIR / "scale_batch_001_fact_records.jsonl"
FAILURE_OUTPUT = INCREMENT_DIR / "scale_batch_001_failure_records.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_001_kb_increment.lock.json"
BATCH_ID = "KB-SCALE-BATCH-001-RESUME01"
TASK_PREFIX = "KB-B001"
SUCCESS_SUMMARIES = (RESUME01, RESUME02)

THEME_TERMS = {
    "ghg_emissions": ("greenhouse gas", "ghg", "scope 1", "scope 2", "scope 3"),
    "energy": ("energy", "electricity", "mwh"),
    "water": ("water",),
    "workforce": ("workforce", "employee", "headcount"),
    "health_safety": ("injury", "fatalit", "safety", "trir"),
    "assurance": ("assurance",),
    "targets": ("target", "net zero", "science-based"),
    "biodiversity": ("biodiversity", "ecosystem", "deforestation"),
    "circularity": ("circular", "recycl", "waste"),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:24]}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records),
        encoding="utf-8",
    )


def successful_outputs() -> dict[tuple[str, int], Path]:
    outputs: dict[tuple[str, int], Path] = {}
    for summary_path in SUCCESS_SUMMARIES:
        summary = read_json(summary_path)
        for record in summary["records"]:
            if record["status"] != "complete":
                continue
            directory = ROOT / record["output_directory"]
            outputs[(record["document_id"], record["page"])] = select_mineru_text_source(
                directory
            )
    return outputs


def candidate_quotes(markdown: str, theme: str) -> list[str]:
    terms = THEME_TERMS[theme]
    lines = [line.strip() for line in markdown.splitlines()]
    usable = [
        line
        for line in lines
        if 25 <= len(line) <= 800
        and not line.startswith("![")
        and any(term in line.casefold() for term in terms)
    ]
    numeric = [line for line in usable if re.search(r"\d", line)]
    selected = numeric[:2] or usable[:1]
    return list(dict.fromkeys(selected))


def build_fact_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config = read_json(SOURCE_CONFIG)
    metadata = {item["document_id"]: item for item in config["documents"]}
    outputs = successful_outputs()
    facts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for document in read_json(TARGETS)["documents"]:
        for target in document["target_pages"]:
            key = (document["document_id"], target["page"])
            markdown_path = outputs[key]
            markdown = read_mineru_text_source(markdown_path)
            source_sha = sha256_file(markdown_path)
            for theme in target["themes"]:
                quotes = candidate_quotes(markdown, theme)
                if not quotes:
                    gaps.append(
                        {
                            "document_id": key[0],
                            "page": key[1],
                            "theme": theme,
                            "reason": "no_theme_line_in_mineru_markdown",
                        }
                    )
                    continue
                for quote_index, quote in enumerate(quotes, start=1):
                    identity = [key[0], key[1], theme, quote]
                    source = metadata[key[0]]
                    facts.append(
                        {
                            "schema_version": "0.1",
                            "record_kind": "fact",
                            "record_id": stable_id("fact", identity),
                            "knowledge_status": "reference_candidate",
                            "trust_tier": "C",
                            "subject": {
                                "task_id": (
                                    f"{TASK_PREFIX}-{key[0]}-P{key[1]:04d}-{theme.upper()}-{quote_index}"
                                ),
                                "entity_label": source["company"],
                                "document_ids": [key[0]],
                                "document_metadata": [
                                    {
                                        "document_id": key[0],
                                        "company": source["company"],
                                        "title": source["title"],
                                        "language": source["language"],
                                        "local_path": source["local_path"],
                                        "sha256": document["document_sha256"],
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
                                "value_origin": "issuer_disclosure_extracted",
                                "reference_period": 2025,
                                "normalized_unit": None,
                                "scope_boundary": None,
                                "calculation_expression": None,
                                "answer_status": "unverified_evidence_candidate",
                            },
                            "evidence": [
                                {"source_id": key[0], "pdf_page": key[1], "quote": quote}
                            ],
                            "provenance": {
                                "source_artifact": markdown_path.relative_to(ROOT).as_posix(),
                                "source_sha256": source_sha,
                                "reference_status": (
                                    "mineru_exact_quote_pending_semantic_projection"
                                ),
                                "simulated": False,
                            },
                            "promotion": {
                                "eligible": False,
                                "reason": (
                                    "requires_atomic_projection_and_independent_evidence_gate"
                                ),
                            },
                        }
                    )
    return facts, gaps


def failure_record(
    *, task_id: str, signature: str, category: str, diagnostic: Any, source: Path
) -> dict[str, Any]:
    identity = [task_id, signature, source.as_posix()]
    return {
        "schema_version": "0.1",
        "record_kind": "failure_observation",
        "record_id": stable_id("failure", identity),
        "experiment_id": BATCH_ID,
        "task_id": task_id,
        "failure_owner": "infrastructure",
        "failure_category": category,
        "failure_signature": signature,
        "observed_stage_states": {"stage": "source_or_parser_acquisition", "status": "failed"},
        "diagnostics": [diagnostic],
        "provenance": {
            "source_artifact": source.relative_to(ROOT).as_posix(),
            "source_sha256": sha256_file(source),
        },
    }


def build_failure_records() -> list[dict[str, Any]]:
    records = []
    for item in read_json(FAILURES)["failures"]:
        records.append(
            failure_record(
                task_id=f"ACQUIRE-{item['document_id']}",
                signature="OFFICIAL_SOURCE_HTTP_403",
                category="cloud_transport",
                diagnostic=item,
                source=FAILURES,
            )
        )
    for item in read_json(INITIAL)["records"]:
        if item["status"] == "failed":
            records.append(
                failure_record(
                    task_id=f"MINERU-{item['document_id']}-P{item['page']:04d}",
                    signature="SANDBOX_LOOPBACK_PORT_DENIED",
                    category="executor_or_configuration",
                    diagnostic=item,
                    source=INITIAL,
                )
            )
    for item in read_json(RESUME01)["records"]:
        if item["status"] == "failed":
            records.append(
                failure_record(
                    task_id=f"MINERU-{item['document_id']}-P{item['page']:04d}-RESUME01",
                    signature="MINERU_POSTPROCESS_RUNTIME_ABORT",
                    category="parser_or_document_structure",
                    diagnostic=item,
                    source=RESUME01,
                )
            )
    return records


def main() -> None:
    facts, gaps = build_fact_records()
    failures = build_failure_records()
    fact_schema = read_json(ROOT / "schemas/knowledge/fact-record-v0.1.schema.json")
    failure_schema = read_json(ROOT / "schemas/knowledge/failure-record-v0.1.schema.json")
    for record in facts:
        Draft202012Validator(fact_schema).validate(record)
    for record in failures:
        Draft202012Validator(failure_schema).validate(record)
    write_jsonl(FACT_OUTPUT, facts)
    write_jsonl(FAILURE_OUTPUT, failures)
    payload = {
        "schema_version": "0.1",
        "batch_id": BATCH_ID,
        "status": "increment_built_candidates_not_promoted",
        "fact_candidates": len(facts),
        "trusted_facts_promoted": 0,
        "evidence_gaps": len(gaps),
        "failure_observations": len(failures),
        "gaps": gaps,
        "outputs": {
            "facts": {"path": FACT_OUTPUT.relative_to(ROOT).as_posix()},
            "failures": {"path": FAILURE_OUTPUT.relative_to(ROOT).as_posix()},
        },
        "policy": {
            "cloud_transmission": False,
            "locked_experiments_modified": False,
            "automatic_promotion": False,
        },
    }
    for output in payload["outputs"].values():
        output["sha256"] = sha256_file(ROOT / output["path"])
    SUMMARY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    reported_keys = ("fact_candidates", "evidence_gaps", "failure_observations")
    print(json.dumps({key: payload[key] for key in reported_keys}))


if __name__ == "__main__":
    main()
