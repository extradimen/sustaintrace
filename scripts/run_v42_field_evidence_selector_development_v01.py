#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / "artifacts/v42_field_evidence_selector_development_v0.1/result.lock.json"
FACT_ID = "fact-ea789b989b68006d3f8b1d4c"
QUOTE = "Cumulative figures (2022 - 2025)"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_v42_development")
    facts = {
        item["record_id"]: item
        for item in (json.loads(line) for line in FACTS.read_text().splitlines() if line)
    }
    fact = facts[FACT_ID]
    selector = {
        "source_id": "P16-SANOFI-SS2025",
        "pdf_page": 90,
        "quote": QUOTE,
    }
    fixture = {
        "fixture_id": stable_id("v42-field-selector-development", selector),
        "gap_signature": "FIELD_EVIDENCE_BINDING_INCOMPLETE",
        "gap_id": "gap-e5c7e621493f223c46e9c",
        "fact_record_id": FACT_ID,
        "native_source": {
            "path": "data/raw/p16_staging/sanofi-sustainability-statement-2025.pdf",
            "sha256": "82547ddb72b6b05dca88f93ed4cfe13010cb5690a5693b96721e9be3ff9c8fcc",
        },
        "evidence_pages": [90],
        "source_literals": [item["quote"] for item in fact["evidence"]],
        "diagnostic_contract": {
            "required_fields": [
                "field_id",
                "collection_cardinality",
                "selected_collection_cardinality",
                "evidence_selector",
                "selected_evidence",
                "evidence_coordinates",
                "unique_binding",
                "blocking_reasons",
            ]
        },
        "adapter_inputs": {"evidence_selector": selector},
        "rollback": {"action": "discard derived development diagnostic"},
    }
    source = ROOT / fixture["native_source"]["path"]
    if sha256_file(source) != fixture["native_source"]["sha256"]:
        raise ValueError("source_hash_mismatch")
    diagnostic = run_read_only_diagnostic(fixture, fact, ROOT)
    observed = diagnostic["diagnostic"]
    contract_passed = (
        diagnostic["status"] == "passed"
        and observed["collection_cardinality"] == 7
        and observed["selected_collection_cardinality"] == 1
        and observed["selected_evidence"] == selector
        and len(observed["evidence_coordinates"]) == 1
    )
    result = {
        "schema_version": "0.1",
        "development_id": "V4.2-FIELD-EVIDENCE-SELECTOR-DEVELOPMENT-V01",
        "status": "development_regression_passed"
        if contract_passed
        else "development_regression_failed",
        "development_source": "already exposed HET-FIELD-NEG-SANOFI-001 only",
        "contract_passed": contract_passed,
        "attempt_count": 1,
        "diagnostic": diagnostic,
        "historical_result_modified": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
        "cloud_transmission_performed": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"contract_passed": contract_passed, "status": diagnostic["status"]}))


if __name__ == "__main__":
    main()
