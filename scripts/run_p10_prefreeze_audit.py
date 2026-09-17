from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.v19_prefreeze_audit import (
    audit_reference_before_candidate,
)
from esg_reliable_discovery.v19_table_period import bind_table_column_periods

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    task_path = "data/tasks/p10_task_pack_v0.1.lock.json"
    registry_path = "data/manifests/p10_mineru_target_registry_RESUME03_v0.1.lock.json"
    contracts_path = "configs/framework/p10_slot_contracts_v0.1.lock.json"
    graph_path = "configs/framework/p10_two_dimensional_table_graph_v0.1.lock.json"
    task_pack = load(task_path)
    registry = load(registry_path)
    contracts = load(contracts_path)["contracts"]
    graph = load(graph_path)

    page_text: dict[int, str] = {}
    for row in registry["pages"]:
        page_text[row["page"]] = (ROOT / row["markdown"]).read_text()
    for table in graph["tables"]:
        page_text[table["pdf_page"]] += "\n" + "\n".join(table["source_strings"])

    audits = {}
    for task in task_pack["tasks"]:
        task_id = task["task_id"]
        reference_path = f"data/annotations/p10_simulated/{task_id}.json"
        reference = load(reference_path)
        fields = [
            slot.get("normalized_field", slot["slot_id"])
            for slot in contracts[task_id]
        ]
        audits[task_id] = audit_reference_before_candidate(
            target_pages=task["target_pages"],
            reference=reference,
            frozen_page_text={page: page_text[page] for page in task["target_pages"]},
            required_normalized_fields=fields,
        )
        audits[task_id]["reference_sha256"] = digest(reference_path)

    calc_binding = bind_table_column_periods(
        inputs=[
            {"value": 69, "period_year": 2025, "evidence_handle": "P369-GHG-R1-C2025"},
            {"value": 73, "period_year": 2024, "evidence_handle": "P369-GHG-R1-C2024"},
        ],
        cells=[
            {
                "handle": "P369-GHG-R1-C2025",
                "row_header": "Gross Scope 1 GHG emissions",
                "column_header": "2025",
                "verbatim_value": "69",
            },
            {
                "handle": "P369-GHG-R1-C2024",
                "row_header": "Gross Scope 1 GHG emissions",
                "column_header": "2024",
                "verbatim_value": "73",
            },
        ],
        required_years=[2025, 2024],
    )

    result = {
        "schema_version": "1.0",
        "experiment_id": task_pack["experiment_id"],
        "status": "passed_release_blocked_only_by_cloud_authorization",
        "framework_version": "v1.9",
        "task_pack_sha256": digest(task_path),
        "parser_registry_sha256": digest(registry_path),
        "slot_contracts_sha256": digest(contracts_path),
        "table_graph_sha256": digest(graph_path),
        "task_audits": audits,
        "calc_two_dimensional_period_binding": calc_binding,
        "candidate_inference_released_by_integrity_gate": True,
        "cloud_transmission_authorized": False,
    }
    output = ROOT / "data/results/p10_v19_prefreeze_integrity_audit_v0.1.lock.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
