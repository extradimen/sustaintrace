from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "V132-SEMANTIC-QUALIFIER-REGRESSION-DEV01"
PROGRESS = ROOT / "data/manifests/v1.3.2_semantic_qualifier_progress.json"
LAYOUT = ROOT / "configs/framework/v1.3.2_layout_assurance_development_registry.lock.json"


def save(records: list[dict[str, object]]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def stage_b(task_id: str, parent: Path, run_id: str) -> dict[str, object]:
    return run_v13_stage_b_task(
        model_config_path=ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
        parent_run_directory=parent,
        task_pack_path=ROOT / "data/tasks/p3_task_pack_v0.1.lock.json",
        acquisition_manifest_path=(
            ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"
        ),
        raw_root=ROOT,
        interventions_root=ROOT / "data/controlled_interventions/p3",
        registry_path=ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
        workspace_root=ROOT,
        layout_registry_path=LAYOUT,
        source_registry_path=ROOT / "data/manifests/p3_source_registry_v0.1.lock.json",
        slot_contracts_path=ROOT / "configs/framework/v1.3_p3_development_slot_contracts.json",
        semantic_qualifiers_path=(
            ROOT / "configs/framework/v1.3.2_semantic_qualifiers.lock.json"
        ),
        system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
        archive_root=ROOT / "research_archive",
        experiment_id=EXPERIMENT,
        run_id=run_id,
        think=None,
    )


def main() -> None:
    records = []
    if PROGRESS.exists():
        records = json.loads(PROGRESS.read_text(encoding="utf-8"))["records"]
    indexed = {item["task_id"]: item for item in records}
    task_id = "P3-XPAGE-002"
    item = indexed.get(task_id, {"task_id": task_id, "retried": False})
    stage_a_id = f"{task_id}-QWEN397B-v132-stage-a-r1"
    parent = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_a_id
    if "stage_a" not in item:
        if parent.exists():
            raise RuntimeError(f"Uncheckpointed Stage A run requires audit: {parent}")
        try:
            item["stage_a_result"] = run_v13_stage_a_task(
                model_config_path=ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
                task_pack_path=ROOT / "data/tasks/p3_task_pack_v0.1.lock.json",
                task_id=task_id,
                acquisition_manifest_path=(
                    ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"
                ),
                raw_root=ROOT,
                interventions_root=ROOT / "data/controlled_interventions/p3",
                registry_path=ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
                workspace_root=ROOT,
                layout_registry_path=LAYOUT,
                system_prompt_path=ROOT / "prompts/v1.0_evidence_reasoning.txt",
                archive_root=ROOT / "research_archive",
                experiment_id=EXPERIMENT,
                run_id=stage_a_id,
                think=None,
            )
            item["stage_a"] = "passed"
        except Exception as error:
            item["stage_a"] = "failed"
            item["stage_a_error"] = f"{type(error).__name__}:{error}"
        records.append(item)
        save(records)
    if item["stage_a"] == "passed" and "stage_b" not in item:
        run_id = f"{task_id}-QWEN397B-v132-stage-b-r1"
        try:
            item["stage_b_result"] = stage_b(task_id, parent, run_id)
            item["stage_b"] = "passed"
        except Exception as error:
            item["stage_b"] = "failed"
            item["stage_b_error"] = f"{type(error).__name__}:{error}"
        save(records)
    task_id = "P3-SCOPE-002"
    if task_id not in indexed:
        parent = (
            ROOT
            / "research_archive/V13-END-TO-END-DEVELOPMENT-DEV01/runs"
            / "P3-SCOPE-002-QWEN397B-v13-e2e-stage-a-r1"
        )
        item = {"task_id": task_id, "retried": False, "stage_a": "reused_frozen_parent"}
        run_id = f"{task_id}-QWEN397B-v132-stage-b-r1"
        try:
            item["stage_b_result"] = stage_b(task_id, parent, run_id)
            item["stage_b"] = "passed"
        except Exception as error:
            item["stage_b"] = "failed"
            item["stage_b_error"] = f"{type(error).__name__}:{error}"
        records.append(item)
        save(records)


if __name__ == "__main__":
    main()
