from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "V13-STAGE-B-TYPE-SCHEMA-DEV02"
PROGRESS = ROOT / "data/manifests/v1.3_stage_b_type_schema_dev02_progress.json"
TASK_ID = "P3-XPAGE-001"
RUN_ID = f"{TASK_ID}-QWEN397B-v13-stage-b-dev02-r1"


def main() -> None:
    if PROGRESS.exists():
        return
    run_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / RUN_ID
    if run_dir.exists():
        raise RuntimeError(f"Uncheckpointed run requires audit: {run_dir}")
    record: dict[str, object] = {"task_id": TASK_ID, "retried": False}
    try:
        record["result"] = run_v13_stage_b_task(
            model_config_path=ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
            parent_run_directory=(
                ROOT
                / "research_archive/V13-END-TO-END-DEVELOPMENT-DEV01/runs"
                / "P3-XPAGE-001-QWEN397B-v13-e2e-stage-a-r1"
            ),
            task_pack_path=ROOT / "data/tasks/p3_task_pack_v0.1.lock.json",
            acquisition_manifest_path=(
                ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"
            ),
            raw_root=ROOT,
            interventions_root=ROOT / "data/controlled_interventions/p3",
            registry_path=ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
            workspace_root=ROOT,
            layout_registry_path=(
                ROOT / "configs/framework/v1.3.1_layout_fallback_development_registry.lock.json"
            ),
            source_registry_path=ROOT / "data/manifests/p3_source_registry_v0.1.lock.json",
            slot_contracts_path=(
                ROOT / "configs/framework/v1.3_p3_development_slot_contracts.json"
            ),
            system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
            archive_root=ROOT / "research_archive",
            experiment_id=EXPERIMENT,
            run_id=RUN_ID,
            think=None,
        )
        record["status"] = "passed"
    except Exception as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}:{error}"
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "records": [record],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
