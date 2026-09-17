from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.binding_screens import screen_period_binding, screen_unit_binding
from esg_reliable_discovery.knowledge_base import sha256_file, stable_id
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manifests/unseen_repair_component_validation_v0.1.lock.json"
RESUME = ROOT / "data/manifests/unseen_repair_component_validation_RESUME03_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / "artifacts/unseen_repair_component_validation_v0.1"


def _load_cases() -> list[dict]:
    base = json.loads(BASE.read_text())
    resume = json.loads(RESUME.read_text())
    overrides = resume["frozen_cases"]["overrides"]
    cases = []
    for case in base["cases"]:
        item = dict(case)
        if case["gap_id"] in overrides:
            item.update(overrides[case["gap_id"]])
        cases.append(item)
    return cases


def _fixture(case: dict, fact: dict) -> dict:
    return {
        "fixture_id": stable_id("unseen-fixture", case),
        "gap_signature": case["component"],
        "gap_id": case["gap_id"],
        "fact_record_id": case["fact_record_id"],
        "native_source": case["source"],
        "evidence_pages": case["pages"],
        "source_literals": [item["quote"] for item in fact.get("evidence", [])],
        "diagnostic_contract": {
            "required_fields": case["expected_contract"].get("required_fields", [])
        },
        "rollback": {"action": "delete derived unseen diagnostic and preserve parents"},
    }


def _contract_passed(case: dict, result: dict) -> bool:
    expected = case["expected_contract"]
    if case["component"] in {"PERIOD_ATTACHMENT_INCOMPLETE", "UNIT_ATTACHMENT_INCOMPLETE"}:
        return result.get("eligibility") == expected["eligibility"]
    if result.get("status") != expected["status"]:
        return False
    diagnostic = result.get("diagnostic", {})
    if case["component"] == "TABLE_CELL_BINDING_INCOMPLETE":
        return (
            expected["row"].casefold() in diagnostic.get("row_header", "").casefold()
            and diagnostic.get("column_header") == expected["column"]
            and diagnostic.get("cell_value") == expected["value"]
        )
    if case["component"] == "NATIVE_PDF_CORROBORATION_INCOMPLETE":
        return diagnostic.get("source_literal") == expected["value"]
    if case["component"] == "CALCULATION_LINEAGE_INCOMPLETE":
        try:
            return round(float(diagnostic["replay_output"]), 2) == expected["value_rounded_2dp"]
        except (KeyError, TypeError, ValueError):
            return False
    return True


def _run(case: dict, fact: dict) -> dict:
    component = case["component"]
    if component == "PERIOD_ATTACHMENT_INCOMPLETE":
        return screen_period_binding(
            {
                "native_source": case["source"],
                "page": case["pages"][0],
                "value": fact["value"],
                "parser_year": "2040",
                "row_label": None,
            },
            ROOT,
        )
    if component == "UNIT_ATTACHMENT_INCOMPLETE":
        marker = "Number of HCPs and HCWs engaged with NCD training programs"
        return screen_unit_binding(
            {
                "native_source": case["source"],
                "page": case["pages"][0],
                "value": fact["value"],
                "row_label": marker,
                "unit_marker_candidates": [marker],
                "bound_quote": " ".join(item["quote"] for item in fact.get("evidence", [])),
                "conversion_required": False,
            },
            ROOT,
        )
    return run_read_only_diagnostic(_fixture(case, fact), fact, ROOT)


def main() -> None:
    summary_path = OUTPUT / "validation_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_unseen_validation")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    facts = {
        item["record_id"]: item
        for item in (json.loads(line) for line in FACTS.read_text().splitlines() if line)
    }
    records = []
    for case in _load_cases():
        if sha256_file(ROOT / case["source"]["path"]) != case["source"]["sha256"]:
            raise ValueError(f"source_hash_mismatch:{case['component']}")
        error = None
        try:
            result = _run(case, facts[case["fact_record_id"]])
        except Exception as exc:  # errors are the unseen validation result, not retries
            result = {"status": "execution_error"}
            error = f"{type(exc).__name__}:{exc}"
        passed = _contract_passed(case, result)
        record = {
            "component": case["component"],
            "gap_id": case["gap_id"],
            "contract_passed": passed,
            "execution_error": error,
            "observed": result,
            "fact_write_performed": False,
            "trust_promotion_performed": False,
        }
        path = OUTPUT / f"{case['component'].lower()}.unseen.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        records.append(
            {
                "component": case["component"],
                "contract_passed": passed,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    summary = {
        "schema_version": "0.1",
        "status": "unseen_component_validation_complete",
        "manifest": str(RESUME.relative_to(ROOT)),
        "manifest_sha256": sha256_file(RESUME),
        "records": records,
        "passed": sum(item["contract_passed"] for item in records),
        "failed": sum(not item["contract_passed"] for item in records),
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "cloud_transmission_performed": False,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"]}))


if __name__ == "__main__":
    main()
