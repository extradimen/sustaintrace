from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "V13-END-TO-END-DEVELOPMENT-DEV01"
PROGRESS = ROOT / "data/manifests/v1.3_end_to_end_development_progress.json"
TASKS = [
    "P3-DEX-001",
    "P3-DEX-002",
    "P3-XPAGE-001",
    "P3-XPAGE-002",
    "P3-SCOPE-001",
    "P3-SCOPE-002",
]
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": ROOT / "data/tasks/p3_task_pack_v0.1.lock.json",
    "acquisition_manifest_path": (
        ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"
    ),
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p3",
    "registry_path": ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
    "workspace_root": ROOT,
    "layout_registry_path": (
        ROOT / "configs/framework/v1.3.1_layout_fallback_development_registry.lock.json"
    ),
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
}


def save(records: list[dict[str, object]]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "development_data_only": True,
                "p3_locked_run_unchanged": True,
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    records = []
    if PROGRESS.exists():
        records = json.loads(PROGRESS.read_text(encoding="utf-8"))["records"]
    indexed = {item["task_id"]: item for item in records}
    for task_id in TASKS:
        item = indexed.get(task_id, {"task_id": task_id, "retried": False})
        stage_a_id = f"{task_id}-QWEN397B-v13-e2e-stage-a-r1"
        stage_a_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_a_id
        if "stage_a" not in item:
            if stage_a_dir.exists():
                raise RuntimeError(f"Uncheckpointed Stage A run requires audit: {stage_a_dir}")
            try:
                item["stage_a_result"] = run_v13_stage_a_task(
                    **COMMON,
                    task_id=task_id,
                    system_prompt_path=ROOT / "prompts/v1.0_evidence_reasoning.txt",
                    run_id=stage_a_id,
                )
                item["stage_a"] = "passed"
            except Exception as error:
                item["stage_a"] = "failed"
                item["stage_a_error"] = f"{type(error).__name__}:{error}"
            if task_id not in indexed:
                records.append(item)
                indexed[task_id] = item
            save(records)
        if item["stage_a"] != "passed" or "stage_b" in item:
            continue
        stage_b_id = f"{task_id}-QWEN397B-v13-e2e-stage-b-r1"
        stage_b_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_b_id
        if stage_b_dir.exists():
            raise RuntimeError(f"Uncheckpointed Stage B run requires audit: {stage_b_dir}")
        try:
            item["stage_b_result"] = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=stage_a_dir,
                source_registry_path=(
                    ROOT / "data/manifests/p3_source_registry_v0.1.lock.json"
                ),
                slot_contracts_path=(
                    ROOT / "configs/framework/v1.3_p3_development_slot_contracts.json"
                ),
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                run_id=stage_b_id,
            )
            item["stage_b"] = "passed"
        except Exception as error:
            item["stage_b"] = "failed"
            item["stage_b_error"] = f"{type(error).__name__}:{error}"
        save(records)


if __name__ == "__main__":
    main()
