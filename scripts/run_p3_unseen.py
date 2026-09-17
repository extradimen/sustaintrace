from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v11_stage_b_runner import run_v11_stage_b_task
from esg_reliable_discovery.v12_stage_a_runner import run_v12_stage_a_task

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P3-UNSEEN-GENERALIZATION-V01"
STAGE_B_TYPES = {"direct_extraction", "cross_page_relation", "scope_subject_boundary"}
TASK_PACK = ROOT / "data/tasks/p3_task_pack_v0.1.lock.json"
PROGRESS = ROOT / "data/manifests/p3_candidate_progress.json"
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": (ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"),
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p3",
    "registry_path": ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
    "workspace_root": ROOT,
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
}


def save(records: list[dict[str, object]]) -> None:
    payload = {
        "schema_version": "1.0",
        "experiment_id": EXPERIMENT,
        "updated_at": datetime.now(UTC).isoformat(),
        "single_attempt_only": True,
        "reference_loaded_by_orchestrator": False,
        "records": records,
    }
    PROGRESS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assert_new_run(run_id: str) -> None:
    run_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / run_id
    if run_dir.exists():
        raise RuntimeError(f"single_attempt_run_already_exists:{run_id}")


def main() -> None:
    pack = json.loads(TASK_PACK.read_text(encoding="utf-8"))
    if not pack.get("inference_allowed"):
        raise RuntimeError("p3_task_pack_not_released_for_inference")
    records: list[dict[str, object]] = []
    save(records)
    for task in pack["tasks"]:
        task_id = task["task_id"]
        task_type = task["task_type"]
        item: dict[str, object] = {
            "task_id": task_id,
            "task_type": task_type,
            "retried": False,
        }
        stage_a_id = f"{task_id}-QWEN397B-stage-a-r1"
        assert_new_run(stage_a_id)
        try:
            result = run_v12_stage_a_task(
                **COMMON,
                task_id=task_id,
                system_prompt_path=ROOT / "prompts/v1.0_evidence_reasoning.txt",
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
        if task_type in STAGE_B_TYPES:
            stage_b_id = f"{task_id}-QWEN397B-stage-b-r1"
            assert_new_run(stage_b_id)
            try:
                result = run_v11_stage_b_task(
                    **COMMON,
                    parent_run_directory=(
                        ROOT / "research_archive" / EXPERIMENT / "runs" / stage_a_id
                    ),
                    ontology_path=(ROOT / "configs/ontology/esg_atomic_claim_registry_v1.0.json"),
                    source_registry_path=(
                        ROOT / "data/manifests/p3_source_registry_v0.1.lock.json"
                    ),
                    projection_contracts_path=(
                        ROOT / "configs/framework/p3_task_projection_contracts_v0.1.lock.json"
                    ),
                    reporting_year_registry_path=(
                        ROOT / "configs/framework/p3_reporting_year_registry_v0.1.lock.json"
                    ),
                    system_prompt_path=ROOT / "prompts/v1.0_atomic_projection.txt",
                    run_id=stage_b_id,
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
