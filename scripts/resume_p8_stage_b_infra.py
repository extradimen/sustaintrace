from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P8-V17-UNSEEN-LOCKBOX-V01"
PARENT = ROOT / "data/manifests/p8_candidate_progress_RESUME02.json"
PROGRESS = ROOT / "data/manifests/p8_candidate_progress_RESUME03.json"
TASK_PACK = ROOT / "data/tasks/p8_execution_task_pack_v0.1.1.lock.json"
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
    PROGRESS.write_text(json.dumps({"schema_version":"1.0","experiment_id":EXPERIMENT,"updated_at":datetime.now(UTC).isoformat(),"parent_progress":str(PARENT.relative_to(ROOT)),"single_attempt_per_stage":True,"reference_loaded_by_orchestrator":False,"records":records},indent=2,sort_keys=True)+"\n")


def main() -> None:
    records = json.loads(PARENT.read_text())["records"]
    if PROGRESS.exists():
        records = json.loads(PROGRESS.read_text())["records"]
    for item in records:
        if item.get("stage_a") != "passed" or item.get("stage_b") == "passed":
            continue
        task_id = item["task_id"]
        stage_a_dir = (
            ROOT
            / "research_archive"
            / EXPERIMENT
            / "runs"
            / f"{task_id}-QWEN397B-v17-stage-a-r1"
        )
        run_id = f"{task_id}-QWEN397B-v17-stage-b-r1-RESUME03"
        run_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / run_id
        if run_dir.exists():
            raise RuntimeError(f"uncheckpointed_stage_b_requires_audit:{run_dir}")
        item.pop("stage_b_error", None)
        try:
            item["stage_b_result"] = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=stage_a_dir,
                source_registry_path=(
                    ROOT / "data/manifests/p8_source_registry_v0.1.lock.json"
                ),
                slot_contracts_path=(
                    ROOT / "configs/framework/p8_slot_contracts_v0.1.1.lock.json"
                ),
                semantic_qualifiers_path=(
                    ROOT / "configs/framework/p8_semantic_qualifiers_v0.1.lock.json"
                ),
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                run_id=run_id,
            )
            item["stage_b"] = "passed"
        except Exception as error:
            item["stage_b"] = "failed"
            item["stage_b_error"] = f"{type(error).__name__}:{error}"
        save(records)


if __name__ == "__main__":
    main()
