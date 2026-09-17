from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from esg_reliable_discovery.evidence_contract_validation import validate_contract_fixture
from esg_reliable_discovery.evidence_repair_triage import index_evidence_contracts
from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_controller import plan_evidence_repair_with_contract

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
SIGNATURES = {
    "EVIDENCE_GROUNDING_MISMATCH",
    "EVIDENCE_SELECTION_GAP",
    "TARGET_ASSURANCE_WINDOW_INCOMPLETE",
}


def main() -> None:
    failures_path = KB / "failure_records.jsonl"
    catalog_path = ROOT / "configs/knowledge/evidence_repair_contract_catalog_v0.1.json"
    catalog = json.loads(catalog_path.read_text())
    contracts = index_evidence_contracts(catalog)
    fixtures = []
    for line in failures_path.read_text().splitlines():
        if not line:
            continue
        failure = json.loads(line)
        if failure["failure_signature"] not in SIGNATURES:
            continue
        plan, binding = plan_evidence_repair_with_contract(
            failure, catalog, mode="operational"
        )
        parent = failure["provenance"]
        fixture = validate_contract_fixture(
            failure=failure,
            binding=binding,
            contract=contracts[plan["causal_subtype"]],
            input_bindings={
                "parent_failure_hash": {
                    "path": parent["source_artifact"],
                    "sha256": parent["source_sha256"],
                }
            },
            root=ROOT,
        )
        fixtures.append(fixture)
    output_path = KB / "exposed_evidence_validation_fixtures.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in fixtures
        )
    )
    result = {
        "schema_version": "0.1",
        "result_id": "ESG-EXPOSED-EVIDENCE-VALIDATION-FIXTURES-v0.1",
        "status": "hashed_parent_fixtures_built_missing_inputs_fail_closed",
        "fixtures": len(fixtures),
        "validation_status_counts": dict(
            Counter(item["validation_status"] for item in fixtures)
        ),
        "all_parent_hashes_valid": all(
            item["checks"]["parent_source_hash_valid"] for item in fixtures
        ),
        "all_rollbacks_prepared_not_executed": all(
            item["rollback_ledger"]["status"] == "prepared_not_executed"
            for item in fixtures
        ),
        "execution_performed": False,
        "inputs": {
            str(failures_path.relative_to(ROOT)): sha256_file(failures_path),
            str(catalog_path.relative_to(ROOT)): sha256_file(catalog_path),
        },
        "output": {
            "path": str(output_path.relative_to(ROOT)),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "supply subtype-specific frozen evidence artifacts without using references "
            "as candidate inputs"
        ),
    }
    result_path = ROOT / "data/results/exposed_evidence_validation_fixtures_v0.1.lock.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
