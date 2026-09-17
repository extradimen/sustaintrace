from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.p1_stage_b_runner import run_p1_stage_b_task
from esg_reliable_discovery.p1_v07_runner import run_p1_v07_task

TASKS = [
    "P2-DEX-002",
    "P2-CALC-001",
    "P2-CALC-002",
    "P2-XPAGE-001",
    "P2-XPAGE-002",
    "P2-SCOPE-001",
    "P2-SCOPE-002",
    "P2-CONFLICT-001",
    "P2-CONFLICT-002",
    "P2-ABSTAIN-001",
    "P2-ABSTAIN-002",
]
STAGE_B_TYPES = {"direct_extraction", "cross_page_relation", "scope_subject_boundary"}
ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P2-LOCKED-HOLDOUT-V01"
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": ROOT / "data/tasks/p2_task_pack_v0.1.lock.json",
    "acquisition_manifest_path": (
        ROOT / "data/manifests/p2_execution_acquisition_manifest_v0.1.lock.json"
    ),
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p2",
    "registry_path": ROOT / "data/manifests/p2_mineru_target_registry_v0.1.json",
    "workspace_root": ROOT,
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
}


def save(records: list[dict]) -> None:
    path = ROOT / "data/manifests/p2_locked_holdout_progress.json"
    payload = {
        "schema_version": "1.0",
        "experiment_id": EXPERIMENT,
        "updated_at": datetime.now(UTC).isoformat(),
        "single_attempt_only": True,
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    pack = json.loads(Path(COMMON["task_pack_path"]).read_text(encoding="utf-8"))
    task_types = {item["task_id"]: item["task_type"] for item in pack["tasks"]}
    records: list[dict] = [
        {
            "task_id": "P2-DEX-001",
            "stage_a": "passed",
            "stage_b": "failed_model_behavior_empty_validated_claims",
            "retried": False,
        }
    ]
    save(records)
    for task_id in TASKS:
        item: dict = {"task_id": task_id, "task_type": task_types[task_id], "retried": False}
        stage_a_id = f"{task_id}-QWEN397B-stage-a-r1"
        try:
            result = run_p1_v07_task(
                **COMMON,
                task_id=task_id,
                system_prompt_path=ROOT / "prompts/p1_synthetic_evaluation_v0.7.txt",
                run_id=stage_a_id,
            )
            item["stage_a"] = "passed"
            item["stage_a_result"] = result
        except Exception as error:
            item["stage_a"] = "failed"
            item["stage_a_error"] = f"{type(error).__name__}:{error}"
            records.append(item)
            save(records)
            continue
        if task_types[task_id] in STAGE_B_TYPES:
            try:
                result = run_p1_stage_b_task(
                    **COMMON,
                    parent_run_directory=(
                        ROOT / "research_archive" / EXPERIMENT / "runs" / stage_a_id
                    ),
                    ontology_path=ROOT / "configs/ontology/esg_atomic_claim_registry_v0.1.json",
                    source_registry_path=ROOT / "data/manifests/p2_source_registry_v0.1.lock.json",
                    system_prompt_path=ROOT / "prompts/p1_stage_b_atomic_claim_v0.1.txt",
                    run_id=f"{task_id}-QWEN397B-stage-b-r1",
                )
                item["stage_b"] = "passed"
                item["stage_b_result"] = result
            except Exception as error:
                item["stage_b"] = "failed"
                item["stage_b_error"] = f"{type(error).__name__}:{error}"
        else:
            item["stage_b"] = "not_required"
        records.append(item)
        save(records)


if __name__ == "__main__":
    main()
