from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/second_unseen_adapter_validation_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / "artifacts/second_unseen_adapter_validation_v0.1"

REQUIRED = {
    "TABLE_CELL_BINDING_INCOMPLETE": [
        "page",
        "row_header",
        "column_header",
        "cell_value",
        "cell_coordinates",
        "parser_native_agreement",
    ],
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": [
        "page",
        "source_literal",
        "parser_literal",
        "normalized_literal",
        "literal_agreement",
        "layout_agreement",
    ],
    "CALCULATION_LINEAGE_INCOMPLETE": [
        "input_cells",
        "operation_graph",
        "replay_output",
        "replay_status",
    ],
}


def _fixture(case: dict, fact: dict) -> dict:
    return {
        "fixture_id": stable_id("second-unseen-fixture", case),
        "gap_signature": case["component"],
        "gap_id": case["gap_id"],
        "fact_record_id": case["fact_record_id"],
        "native_source": case["source"],
        "evidence_pages": case["pages"],
        "source_literals": [item["quote"] for item in fact["evidence"]],
        "diagnostic_contract": {"required_fields": REQUIRED[case["component"]]},
        "adapter_inputs": case["adapter_inputs"],
        "rollback": {"action": "delete derived second-unseen diagnostic"},
    }


def _contract_passed(case: dict, result: dict) -> bool:
    expected = case["expected_contract"]
    if result.get("status") != expected["status"]:
        return False
    diagnostic = result.get("diagnostic", {})
    if case["component"] == "TABLE_CELL_BINDING_INCOMPLETE":
        return (
            expected["row_contains"].casefold()
            in diagnostic.get("row_header", "").casefold()
            and diagnostic.get("column_header") == expected["column"]
            and diagnostic.get("cell_value") == expected["value"]
        )
    if case["component"] == "NATIVE_PDF_CORROBORATION_INCOMPLETE":
        return diagnostic.get("source_literal") == expected["value"]
    try:
        return (
            diagnostic.get("operation_graph", [{}])[0].get("operation")
            == expected["operation"]
            and round(float(diagnostic["replay_output"]), 2) == expected["value"]
        )
    except (KeyError, TypeError, ValueError):
        return False


def main() -> None:
    summary_path = OUTPUT / "validation_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_second_unseen_validation")
    manifest = json.loads(MANIFEST.read_text())
    facts = {
        item["record_id"]: item
        for item in (json.loads(line) for line in FACTS.read_text().splitlines() if line)
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for case in manifest["cases"]:
        if sha256_file(ROOT / case["source"]["path"]) != case["source"]["sha256"]:
            raise ValueError(f"source_hash_mismatch:{case['component']}")
        error = None
        try:
            observed = run_read_only_diagnostic(
                _fixture(case, facts[case["fact_record_id"]]),
                facts[case["fact_record_id"]],
                ROOT,
            )
        except Exception as exc:  # unseen component failures are archived, never retried
            observed = {"status": "execution_error"}
            error = f"{type(exc).__name__}:{exc}"
        passed = _contract_passed(case, observed)
        record = {
            "component": case["component"],
            "gap_id": case["gap_id"],
            "fact_record_id": case["fact_record_id"],
            "contract_passed": passed,
            "execution_error": error,
            "observed": observed,
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
        "status": "second_unseen_adapter_validation_complete",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST),
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
