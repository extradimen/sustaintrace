from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P10-V19-INFRA-RECOVERY-01"
PROGRESS = ROOT / "data/manifests/p10_infra_recovery_progress.json"
TASK_PACK = ROOT / "data/tasks/p10_execution_task_pack_v0.1.1.lock.json"
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": ROOT / "data/manifests/p10_source_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p10",
    "registry_path": ROOT / "data/manifests/p10_mineru_executor_registry_RESUME01_v0.1.lock.json",
    "workspace_root": ROOT,
    "layout_registry_path": (
        ROOT / "configs/framework/p10_layout_fallback_registry_v0.1.1.lock.json"
    ),
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
    "use_v15_grounding": True,
}


def save(records: dict[str, dict[str, object]]) -> None:
    payload = {
        "schema_version": "1.0",
        "experiment_id": EXPERIMENT,
        "parent_experiment": "P10-V19-UNSEEN-LOCKBOX-V01",
        "recovery_scope": [
            "P10-SAFETY-001:stage_b",
            "P10-CALC-001:stage_a",
            "P10-TARGET-001:stage_a",
        ],
        "updated_at": datetime.now(UTC).isoformat(),
        "original_lockbox_modified": False,
        "single_recovery_attempt_per_stage": True,
        "records": records,
    }
    PROGRESS.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    records = json.loads(PROGRESS.read_text())["records"] if PROGRESS.exists() else {}
    parent = ROOT / "research_archive/P10-V19-UNSEEN-LOCKBOX-V01/runs"
    key = "P10-SAFETY-001:stage_b"
    if key not in records:
        try:
            result = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=(
                    parent / "P10-SAFETY-001-QWEN397B-v19-stage-a-RESUME01"
                ),
                source_registry_path=(
                    ROOT / "data/manifests/p10_source_registry_v0.1.lock.json"
                ),
                slot_contracts_path=(
                    ROOT / "configs/framework/p10_slot_contracts_v0.1.1.lock.json"
                ),
                semantic_qualifiers_path=(
                    ROOT / "configs/framework/p10_semantic_qualifiers_v0.1.lock.json"
                ),
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                run_id="P10-SAFETY-001-QWEN397B-v19-stage-b-INFRA-RECOVERY01",
            )
            records[key] = {"status": "passed", "result": result}
        except Exception as error:
            records[key] = {
                "status": "failed",
                "error": f"{type(error).__name__}:{error}",
            }
        save(records)
    for task_id in ("P10-CALC-001", "P10-TARGET-001"):
        key = f"{task_id}:stage_a"
        if key in records:
            continue
        try:
            result = run_v13_stage_a_task(
                **COMMON,
                task_id=task_id,
                system_prompt_path=ROOT / "prompts/v1.0_evidence_reasoning.txt",
                run_id=f"{task_id}-QWEN397B-v19-stage-a-INFRA-RECOVERY01",
            )
            records[key] = {"status": "passed", "result": result}
        except Exception as error:
            records[key] = {
                "status": "failed",
                "error": f"{type(error).__name__}:{error}",
            }
        save(records)


if __name__ == "__main__":
    main()
