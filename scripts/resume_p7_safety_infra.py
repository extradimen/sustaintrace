from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P7-V16-UNSEEN-LOCKBOX-V01-RESUME01"
PROGRESS = ROOT / "data/manifests/p7_candidate_progress_RESUME01.json"
TASK_PACK = ROOT / "data/tasks/p7_execution_task_pack_v0.1.1.lock.json"
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": ROOT / "data/manifests/p7_source_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p7",
    "registry_path": ROOT / "data/manifests/p7_mineru_target_registry_RESUME01_v0.1.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT / "configs/framework/p7_layout_fallback_registry_v0.1.lock.json",
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
    "use_v15_grounding": True,
}


def save(record: dict[str, object]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": EXPERIMENT,
                "parent_experiment_id": "P7-V16-UNSEEN-LOCKBOX-V01",
                "updated_at": datetime.now(UTC).isoformat(),
                "records": [record],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    task_id = "P7-SAFETY-001"
    record = (
        json.loads(PROGRESS.read_text(encoding="utf-8"))["records"][0]
        if PROGRESS.exists()
        else {"task_id": task_id, "retried_for_infrastructure_only": True}
    )
    stage_a_id = f"{task_id}-QWEN397B-v16-stage-a-RESUME01"
    stage_a_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_a_id
    if "stage_a" not in record:
        if stage_a_dir.exists():
            raise RuntimeError(f"uncheckpointed_stage_a_requires_audit:{stage_a_dir}")
        try:
            record["stage_a_result"] = run_v13_stage_a_task(
                **COMMON,
                task_id=task_id,
                system_prompt_path=ROOT / "prompts/v1.0_evidence_reasoning.txt",
                run_id=stage_a_id,
            )
            record["stage_a"] = "passed"
        except Exception as error:
            record["stage_a"] = "failed"
            record["stage_a_error"] = f"{type(error).__name__}:{error}"
        save(record)
    if record["stage_a"] != "passed" or "stage_b" in record:
        return
    stage_b_id = f"{task_id}-QWEN397B-v16-stage-b-RESUME01"
    stage_b_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_b_id
    if stage_b_dir.exists():
        raise RuntimeError(f"uncheckpointed_stage_b_requires_audit:{stage_b_dir}")
    try:
        record["stage_b_result"] = run_v13_stage_b_task(
            **COMMON,
            parent_run_directory=stage_a_dir,
            source_registry_path=ROOT / "data/manifests/p7_source_registry_v0.1.lock.json",
            slot_contracts_path=ROOT / "configs/framework/p7_slot_contracts_v0.1.lock.json",
            semantic_qualifiers_path=(
                ROOT / "configs/framework/p7_semantic_qualifiers_v0.1.lock.json"
            ),
            system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
            run_id=stage_b_id,
        )
        record["stage_b"] = "passed"
    except Exception as error:
        record["stage_b"] = "failed"
        record["stage_b_error"] = f"{type(error).__name__}:{error}"
    save(record)


if __name__ == "__main__":
    main()
