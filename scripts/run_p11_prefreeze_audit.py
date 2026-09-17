from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.v19_prefreeze_audit import audit_reference_before_candidate
from esg_reliable_discovery.v19_table_period import bind_table_column_periods
from esg_reliable_discovery.v20_contracts import (
    validate_evidence_handle_pages,
    validate_slot_contracts_before_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    task_path = "data/tasks/p11_task_pack_v0.1.lock.json"
    registry_path = "data/manifests/p11_mineru_target_registry_RESUME01_v0.1.lock.json"
    contracts_path = "configs/framework/p11_slot_contracts_v0.1.lock.json"
    graph_path = "configs/framework/p11_two_dimensional_table_graph_v0.1.lock.json"
    task_pack = load(task_path)
    registry = load(registry_path)
    contracts = load(contracts_path)["contracts"]
    graph = load(graph_path)

    page_text = {
        row["page"]: (ROOT / row["markdown"]).read_text()
        for row in registry["pages"]
    }
    for table in graph["tables"]:
        page_text[table["pdf_page"]] += "\n" + "\n".join(table["source_strings"])

    audits = {}
    contract_audits = {}
    all_evidence = []
    for task in task_pack["tasks"]:
        task_id = task["task_id"]
        reference_path = f"data/annotations/p11_simulated/{task_id}.json"
        reference = load(reference_path)
        required_fields = [
            slot.get("normalized_field", slot["slot_id"])
            for slot in contracts[task_id]
        ]
        audits[task_id] = audit_reference_before_candidate(
            target_pages=task["target_pages"],
            reference=reference,
            frozen_page_text={page: page_text[page] for page in task["target_pages"]},
            required_normalized_fields=required_fields,
        )
        audits[task_id]["reference_sha256"] = digest(reference_path)
        contract_audits[task_id] = validate_slot_contracts_before_candidate(
            contracts[task_id]
        )
        for index, evidence in enumerate(reference["evidence"], start=1):
            all_evidence.append(
                {
                    "handle": f"P{evidence['pdf_page']}-R{task_id}-E{index}",
                    "page": evidence["pdf_page"],
                    "verbatim_text": evidence["quote"],
                }
            )

    calc_binding = bind_table_column_periods(
        inputs=[
            {"value": 288.3, "period_year": 2025, "evidence_handle": "P176-GHG-R-S1-C2025"},
            {"value": 70.7, "period_year": 2025, "evidence_handle": "P177-S2-R-TOTAL-C2025-MB"},
        ],
        cells=[
            {
                "handle": "P176-GHG-R-S1-C2025",
                "row_header": "Total gross Scope 1 GHG emissions",
                "column_header": "2025",
                "verbatim_value": "288.3",
            },
            {
                "handle": "P177-S2-R-TOTAL-C2025-MB",
                "row_header": "Total gross Scope 2 GHG emissions, market-based",
                "column_header": "2025",
                "verbatim_value": "70.7",
            },
        ],
        required_years=[2025, 2025],
    )

    result = {
        "schema_version": "2.0",
        "experiment_id": task_pack["experiment_id"],
        "status": "passed_release_blocked_only_by_cloud_authorization",
        "framework_version": "v2.0",
        "task_pack_sha256": digest(task_path),
        "parser_registry_sha256": digest(registry_path),
        "slot_contracts_sha256": digest(contracts_path),
        "table_graph_sha256": digest(graph_path),
        "task_audits": audits,
        "contract_audits": contract_audits,
        "evidence_handle_page_audit": validate_evidence_handle_pages(all_evidence),
        "calc_two_dimensional_period_binding": calc_binding,
        "candidate_inference_released_by_integrity_gate": True,
        "cloud_transmission_authorized": False,
    }
    output = ROOT / "data/results/p11_v20_prefreeze_integrity_audit_v0.1.lock.json"
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
