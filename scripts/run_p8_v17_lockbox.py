from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P8-V17-UNSEEN-LOCKBOX-V01"
PROGRESS = ROOT / "data/manifests/p8_candidate_progress_RESUME01.json"
TASK_PACK = ROOT / "data/tasks/p8_execution_task_pack_v0.1.1.lock.json"
STAGE_B_TYPES = {"direct_extraction", "scope_subject_boundary"}
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": ROOT / "data/manifests/p8_source_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p8",
    "registry_path": ROOT / "data/manifests/p8_mineru_target_registry_RESUME04_v0.1.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT / "configs/framework/p8_layout_fallback_registry_v0.1.lock.json",
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
    "use_v15_grounding": True,
}


def save(records: list[dict[str, object]]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "single_attempt_per_stage": True,
                "reference_loaded_by_orchestrator": False,
                "cloud_authorization": "data/manifests/p8_cloud_authorization_2026-09-06.lock.json",
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    pack = json.loads(TASK_PACK.read_text(encoding="utf-8"))
    if not pack.get("inference_allowed"):
        raise RuntimeError("p8_task_pack_not_released")
    records = (
        json.loads(PROGRESS.read_text(encoding="utf-8"))["records"]
        if PROGRESS.exists()
        else []
    )
    indexed = {item["task_id"]: item for item in records}
    for task in pack["tasks"]:
        task_id = task["task_id"]
        item = indexed.get(
            task_id,
            {"task_id": task_id, "task_type": task["task_type"], "retried": False},
        )
        stage_a_id = f"{task_id}-QWEN397B-v17-stage-a-r1"
        stage_a_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_a_id
        if "stage_a" not in item:
            if stage_a_dir.exists():
                raise RuntimeError(f"uncheckpointed_stage_a_requires_audit:{stage_a_dir}")
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
        if task["task_type"] not in STAGE_B_TYPES:
            item["stage_b"] = "not_required"
            save(records)
            continue
        stage_b_id = f"{task_id}-QWEN397B-v17-stage-b-r1"
        stage_b_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_b_id
        if stage_b_dir.exists():
            raise RuntimeError(f"uncheckpointed_stage_b_requires_audit:{stage_b_dir}")
        try:
            item["stage_b_result"] = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=stage_a_dir,
                source_registry_path=ROOT / "data/manifests/p8_source_registry_v0.1.lock.json",
                slot_contracts_path=ROOT / "configs/framework/p8_slot_contracts_v0.1.lock.json",
                semantic_qualifiers_path=(
                    ROOT / "configs/framework/p8_semantic_qualifiers_v0.1.lock.json"
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
