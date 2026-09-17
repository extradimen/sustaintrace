#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.diagnostic_preflight import (
    run_preflighted_read_only_diagnostic,
)
from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
SOURCE = ROOT / "data/manifests/heterogeneous_component_validation_RESUME01_v0.1.lock.json"
ARTIFACT = ROOT / "artifacts/v43_parent_binding_preflight_development_v0.1/result.lock.json"
ARCHIVE = ROOT / "data/results/v43_parent_binding_preflight_development_v0.1.lock.json"
POSITIVE_FACT = "fact-9563920c088f89c3fc9f0b75"
POSITIVE_GAP = "gap-014f6bb663198ffdf540e6e4"


def _fixture(case: dict) -> dict:
    return {
        "fixture_id": case["case_id"],
        "fact_record_id": case["fact_record_id"],
        "gap_id": case["gap_id"],
        "gap_signature": case["component"],
    }


def main() -> None:
    for output in (ARTIFACT, ARCHIVE):
        if output.exists():
            raise FileExistsError(f"refusing_to_overwrite:{output}")
    before = {"facts": sha256_file(FACTS), "gaps": sha256_file(GAPS)}
    manifest = json.loads(SOURCE.read_text())
    negative_cases = [
        case
        for case in manifest["cases"]
        if case["case_id"]
        in {"HET-CALC-POS-SHELL-001", "HET-CALC-POS-TOTALENERGIES-001"}
    ]
    if len(negative_cases) != 2:
        raise ValueError("exposed_negative_cases_not_unique")

    def forbidden_runner(*args):
        raise AssertionError(f"blocked case invoked adapter:{args}")

    negatives = [
        run_preflighted_read_only_diagnostic(
            fixture=_fixture(case),
            satisfied_dimensions=["calculation_lineage"],
            root=ROOT,
            fact_store_path=FACTS,
            gap_store_path=GAPS,
            diagnostic_runner=forbidden_runner,
        )
        for case in negative_cases
    ]

    positive_calls = []

    def sentinel_runner(fixture, fact, root):
        positive_calls.append((fixture["fixture_id"], fact["record_id"], root == ROOT))
        return {
            "status": "passed",
            "fixture_id": fixture["fixture_id"],
            "fact_record_id": fact["record_id"],
            "adapter": "development_sentinel_no_historical_diagnostic_rerun",
        }

    positive = run_preflighted_read_only_diagnostic(
        fixture={
            "fixture_id": "V43-POSITIVE-P22-WATER-CALC-PARENT-BINDING",
            "fact_record_id": POSITIVE_FACT,
            "gap_id": POSITIVE_GAP,
            "gap_signature": "CALCULATION_LINEAGE_INCOMPLETE",
        },
        satisfied_dimensions=["calculation_lineage"],
        root=ROOT,
        fact_store_path=FACTS,
        gap_store_path=GAPS,
        diagnostic_runner=sentinel_runner,
    )
    after = {"facts": sha256_file(FACTS), "gaps": sha256_file(GAPS)}
    contract_passed = (
        all(item["status"] == "blocked_before_execution" for item in negatives)
        and all(item["adapter_invocation_count"] == 0 for item in negatives)
        and all(
            item["preflight"]["blocking_reasons"] == ["PARENT_GAP_NOT_REGISTERED"]
            for item in negatives
        )
        and positive["status"] == "completed"
        and positive["adapter_invocation_count"] == 1
        and len(positive_calls) == 1
        and before == after
    )
    result = {
        "schema_version": "0.1",
        "development_id": "V4.3-DIAGNOSTIC-PARENT-BINDING-PREFLIGHT-V01",
        "status": (
            "development_regression_passed"
            if contract_passed
            else "development_regression_failed"
        ),
        "contract_passed": contract_passed,
        "negative_regressions": negatives,
        "positive_regression": positive,
        "positive_adapter_calls": positive_calls,
        "immutable_store_sha256_before": before,
        "immutable_store_sha256_after": after,
        "source_manifest": {"path": str(SOURCE), "sha256": sha256_file(SOURCE)},
        "historical_result_modified": False,
        "parent_gap_fabricated": False,
        "fact_write_performed": False,
        "gap_write_performed": False,
        "trust_promotion_performed": False,
        "cloud_transmission_performed": False,
    }
    for output in (ARTIFACT, ARCHIVE):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "contract_passed": contract_passed,
                "negative_adapter_calls": sum(
                    item["adapter_invocation_count"] for item in negatives
                ),
                "positive_adapter_calls": len(positive_calls),
            }
        )
    )


if __name__ == "__main__":
    main()
