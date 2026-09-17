#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/v39_volvo_repeated_value_table_unseen_v0.1.lock.json"
RESUME = ROOT / "data/manifests/v39_volvo_repeated_value_table_unseen_RESUME01_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / "artifacts/v39_volvo_repeated_value_table_unseen_RESUME01_v0.1/result.lock.json"


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("frozen unseen result already exists; refusing duplicate execution")
    manifest = json.loads(MANIFEST.read_text())
    resume = json.loads(RESUME.read_text())
    case = dict(manifest["case"])
    case["fixture_id"] = resume["resume_scope"]["identity_mapping"]["fixture_id"]
    facts = {
        item["record_id"]: item
        for item in (json.loads(line) for line in FACTS.read_text().splitlines() if line)
    }
    fact = facts[case["fact_record_id"]]
    result = run_read_only_diagnostic(case, fact, ROOT)
    diagnostic = result.get("diagnostic", {})
    expected = case["expected"]
    contract_passed = (
        result.get("status") == expected["outcome"]
        and diagnostic.get("row_header") == expected["row_equals"]
        and diagnostic.get("column_header") == expected["period"]
        and diagnostic.get("cell_value") == expected["value"]
        and diagnostic.get("cell_coordinates", {}).get("x0")
        == expected["expected_target_cell_x0"]
    )
    archive = {
        "schema_version": "0.1",
        "experiment_id": resume["experiment_id"],
        "status": "completed",
        "attempt_count": 1,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST),
        "resume_manifest": str(RESUME.relative_to(ROOT)),
        "resume_manifest_sha256": sha256_file(RESUME),
        "case_id": case["case_id"],
        "raw_result": result,
        "contract_passed": contract_passed,
        "historical_results_modified": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
        "cloud_transmission_performed": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
