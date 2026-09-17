from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.p1_stage_b_runner import build_stage_b_packet
from esg_reliable_discovery.p1_v06_runner import build_v066_packet_from_registry
from esg_reliable_discovery.v1_stage_b import validate_and_project_v1

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P2-LOCKED-HOLDOUT-V01"
TASKS = ["P2-DEX-001", "P2-XPAGE-001", "P2-XPAGE-002", "P2-SCOPE-001", "P2-SCOPE-002"]


def main() -> None:
    ontology = json.loads(
        (ROOT / "configs/ontology/esg_atomic_claim_registry_v1.0.json").read_text()
    )
    contracts = json.loads(
        (ROOT / "configs/framework/v1.0_task_projection_contracts.json").read_text()
    )["contracts"]
    records = []
    for task_id in TASKS:
        stage_a = ROOT / "research_archive" / EXPERIMENT / "runs" / f"{task_id}-QWEN397B-stage-a-r1"
        stage_b = ROOT / "research_archive" / EXPERIMENT / "runs" / f"{task_id}-QWEN397B-stage-b-r1"
        _, _, handles = build_v066_packet_from_registry(
            task_pack_path=ROOT / "data/tasks/p2_task_pack_v0.1.lock.json",
            task_id=task_id,
            acquisition_manifest_path=ROOT
            / "data/manifests/p2_execution_acquisition_manifest_v0.1.lock.json",
            raw_root=ROOT,
            interventions_root=ROOT / "data/controlled_interventions/p2",
            registry_path=ROOT / "data/manifests/p2_mineru_target_registry_v0.1.json",
            workspace_root=ROOT,
            split_table_rows=True,
        )
        try:
            _, _, evidence, _, subject = build_stage_b_packet(
                parent_run_directory=stage_a,
                available_handles=handles,
                ontology_path=ROOT / "configs/ontology/esg_atomic_claim_registry_v0.1.json",
                source_registry_path=ROOT / "data/manifests/p2_source_registry_v0.1.lock.json",
            )
            output = json.loads((stage_b / "model_generated_content.json").read_text())
            validate_and_project_v1(output, evidence, ontology, subject, contracts[task_id])
            records.append({"task_id": task_id, "v1_retrospective_gate": "passed"})
        except Exception as error:
            records.append(
                {
                    "task_id": task_id,
                    "v1_retrospective_gate": "rejected",
                    "reason": f"{type(error).__name__}:{error}",
                }
            )
    output = ROOT / "data/results/p2_stage_b_v1_retrospective_audit.json"
    output.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "development_diagnostic_not_fresh_inference",
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
