from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_controller import plan_evidence_repair_with_contract

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
SIGNATURES = {
    "EVIDENCE_GROUNDING_MISMATCH",
    "EVIDENCE_SELECTION_GAP",
    "TARGET_ASSURANCE_WINDOW_INCOMPLETE",
}


def load_failures(path: Path) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record["failure_signature"] in SIGNATURES:
            records.append(record)
    return records


def main() -> None:
    failures_path = KB / "failure_records.jsonl"
    catalog_path = ROOT / "configs/knowledge/evidence_repair_contract_catalog_v0.1.json"
    schema_path = ROOT / "schemas/knowledge/evidence-repair-contract-binding-v0.1.schema.json"
    catalog = json.loads(catalog_path.read_text())
    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    frozen = []
    operational_preview = []
    for failure in load_failures(failures_path):
        _, locked_binding = plan_evidence_repair_with_contract(
            failure, catalog, mode="locked_evaluation"
        )
        _, operational_binding = plan_evidence_repair_with_contract(
            failure, catalog, mode="operational"
        )
        errors = list(validator.iter_errors(locked_binding)) + list(
            validator.iter_errors(operational_binding)
        )
        if errors:
            raise ValueError(f"contract binding invalid: {[error.message for error in errors]}")
        frozen.append(locked_binding)
        operational_preview.append(operational_binding)

    output_path = KB / "exposed_evidence_contract_bindings.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in frozen
        )
    )
    preview_path = KB / "exposed_evidence_operational_route_preview.jsonl"
    preview_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in operational_preview
        )
    )
    result = {
        "schema_version": "0.1",
        "result_id": "ESG-EVIDENCE-REPAIR-CONTRACT-BINDINGS-v0.1",
        "status": "contracts_frozen_and_controller_integrated_no_execution",
        "locked_bindings": len(frozen),
        "locked_decisions": dict(Counter(item["decision"] for item in frozen)),
        "operational_preview_decisions": dict(
            Counter(item["decision"] for item in operational_preview)
        ),
        "contract_ids": sorted({item["contract_id"] for item in frozen}),
        "execution_performed": False,
        "candidate_output_rewritten": False,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            str(failures_path.relative_to(ROOT)): sha256_file(failures_path),
            str(catalog_path.relative_to(ROOT)): sha256_file(catalog_path),
            str(schema_path.relative_to(ROOT)): sha256_file(schema_path),
        },
        "outputs": {
            str(output_path.relative_to(ROOT)): sha256_file(output_path),
            str(preview_path.relative_to(ROOT)): sha256_file(preview_path),
        },
        "next_gate": "instantiate per-subtype validation fixtures on exposed failures",
    }
    result_path = ROOT / "data/results/evidence_repair_contract_bindings_v0.1.lock.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["operational_preview_decisions"], sort_keys=True))


if __name__ == "__main__":
    main()
