from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.binding_screens import (
    screen_period_binding,
    screen_unit_binding,
)
from esg_reliable_discovery.knowledge_base import sha256_file, stable_id
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / (
    "data/manifests/heterogeneous_component_validation_RESUME01_v0.1.lock.json"
)
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / "artifacts/heterogeneous_component_validation_v0.1"


def _fixture(case: dict, fact: dict) -> dict:
    return {
        "fixture_id": stable_id("heterogeneous-component-fixture", case),
        "gap_signature": case["component"],
        "gap_id": case["gap_id"],
        "fact_record_id": case["fact_record_id"],
        "native_source": case["source"],
        "evidence_pages": case["pages"],
        "source_literals": [item["quote"] for item in fact["evidence"]],
        "diagnostic_contract": {"required_fields": case["required_fields"]},
        "adapter_inputs": case.get("adapter_inputs", {}),
        "rollback": {"action": "delete heterogeneous validation diagnostic"},
    }


def _execute(case: dict, fact: dict) -> dict:
    if case["runner"] == "read_only":
        return run_read_only_diagnostic(_fixture(case, fact), fact, ROOT)
    inputs = {**case["adapter_inputs"], "native_source": case["source"]}
    if case["runner"] == "period_screen":
        return screen_period_binding(inputs, ROOT)
    if case["runner"] == "unit_screen":
        return screen_unit_binding(inputs, ROOT)
    raise ValueError(f"unsupported_runner:{case['runner']}")


def _contract_passed(case: dict, observed: dict, error: str | None) -> bool:
    expected = case["expected"]
    outcome = expected["outcome"]
    if outcome == "not_passed":
        return error is not None or observed.get("status") != "passed"
    if error is not None:
        return False
    if outcome == "blocked":
        return observed.get("status") == "blocked"
    if outcome in {"eligible", "ineligible"}:
        if observed.get("eligibility") != outcome:
            return False
        reason = expected.get("blocking_reason")
        if reason and reason not in observed.get("blocking_reasons", []):
            return False
        return (
            outcome == "ineligible"
            or (
                observed.get("bound_period") == expected["period"]
                and float(observed.get("bound_value")) == float(expected["value"])
            )
        )
    if observed.get("status") != "passed":
        return False
    diagnostic = observed.get("diagnostic", {})
    if case["component"] == "TABLE_CELL_BINDING_INCOMPLETE":
        return (
            expected["row_contains"].casefold()
            in diagnostic.get("row_header", "").casefold()
            and diagnostic.get("column_header") == expected["period"]
            and diagnostic.get("cell_value") == expected["value"]
        )
    if case["component"] == "NATIVE_PDF_CORROBORATION_INCOMPLETE":
        return diagnostic.get("source_literal") == expected["value"]
    if case["component"] == "CALCULATION_LINEAGE_INCOMPLETE":
        try:
            return (
                diagnostic["operation_graph"][0]["operation"] == expected["operation"]
                and [float(item["value"]) for item in diagnostic["input_cells"]]
                == expected["inputs"]
                and float(diagnostic["replay_output"]) == expected["value"]
                and diagnostic["replay_status"] == "passed"
            )
        except (KeyError, TypeError, ValueError):
            return False
    return False


def main() -> None:
    summary_path = OUTPUT / "validation_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_heterogeneous_validation")
    manifest = json.loads(MANIFEST.read_text())
    facts = {
        item["record_id"]: item
        for item in (json.loads(line) for line in FACTS.read_text().splitlines() if line)
    }
    OUTPUT.mkdir(parents=True, exist_ok=False)
    records = []
    for case in manifest["cases"]:
        if sha256_file(ROOT / case["source"]["path"]) != case["source"]["sha256"]:
            raise ValueError(f"source_hash_mismatch:{case['case_id']}")
        error = None
        try:
            observed = _execute(case, facts[case["fact_record_id"]])
        except Exception as exc:  # exactly one attempt; preserve behavior
            observed = {"status": "execution_error"}
            error = f"{type(exc).__name__}:{exc}"
        passed = _contract_passed(case, observed, error)
        record = {
            "schema_version": "0.1",
            "record_kind": "heterogeneous_component_validation_case",
            "case_id": case["case_id"],
            "component": case["component"],
            "polarity": case["polarity"],
            "contract_passed": passed,
            "execution_error": error,
            "observed": observed,
            "attempts": 1,
            "fact_write_performed": False,
            "trust_promotion_performed": False,
        }
        path = OUTPUT / f"{case['case_id'].lower()}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        records.append(
            {
                "case_id": case["case_id"],
                "component": case["component"],
                "polarity": case["polarity"],
                "contract_passed": passed,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    summary = {
        "schema_version": "0.1",
        "record_kind": "heterogeneous_component_validation_summary",
        "status": "heterogeneous_component_validation_complete",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST),
        "records": records,
        "passed": sum(item["contract_passed"] for item in records),
        "failed": sum(not item["contract_passed"] for item in records),
        "coverage_limits": manifest["coverage_limits"],
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
        "cloud_transmission_performed": False,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"]}))


if __name__ == "__main__":
    main()
