from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task
from esg_reliable_discovery.v20_failure_taxonomy import classify_failure

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P19-V28-UNSEEN-LOCKBOX-V01"
PROGRESS = ROOT / "data/manifests/p19_candidate_progress.json"
TASK_PACK = ROOT / "data/tasks/p19_local_execution_task_pack_v0.1.lock.json"
RELEASE = ROOT / "data/tasks/p19_execution_release_v0.1.lock.json"
EXPECTED_PAGES = [58, 65, 66, 80, 123, 124, 135, 136]
STAGE_B_TYPES = {"direct_extraction_and_relation", "scope_subject_boundary"}
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": ROOT / "data/manifests/p19_source_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p19",
    "registry_path": ROOT / "data/manifests/p19_mineru_target_registry_v0.1.lock.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT / "configs/framework/p19_layout_fallback_registry_v0.1.lock.json",
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
    "use_v15_grounding": True,
}


def save(records: list[dict[str, object]]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "2.8",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "single_attempt_per_stage": True,
                "reference_loaded_by_orchestrator": False,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def validate_release() -> None:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    if not release.get("inference_allowed"):
        raise RuntimeError("p19_task_pack_not_released")
    authorization = json.loads((ROOT / release["exact_authorization_record"]).read_text())
    if authorization.get("status") != "authorized_by_user":
        raise RuntimeError("p19_cloud_authorization_invalid")
    if (
        authorization.get("pages") != EXPECTED_PAGES
        or authorization.get("model") != "qwen3.5:397b-cloud"
        or authorization.get("experiment_scope")
        != "P19 Stage A/Stage B single-attempt candidate inference"
    ):
        raise RuntimeError("p19_cloud_authorization_scope_mismatch")
    readiness = json.loads(
        (ROOT / "data/results/p19_v28_local_validation_v0.1.lock.json").read_text()
    )
    expected = "local_validation_passed_waiting_for_payload_specific_cloud_authorization"
    if readiness.get("status") != expected:
        raise RuntimeError("p19_prefreeze_audit_not_passed")


def main() -> None:
    validate_release()
    pack = json.loads(TASK_PACK.read_text(encoding="utf-8"))
    records = json.loads(PROGRESS.read_text())["records"] if PROGRESS.exists() else []
    indexed = {item["task_id"]: item for item in records}
    for task in pack["tasks"]:
        task_id = task["task_id"]
        item = indexed.get(
            task_id,
            {"task_id": task_id, "task_type": task["task_type"], "retried": False},
        )
        stage_a_id = f"{task_id}-QWEN397B-v28-stage-a"
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
                    use_v21_calculation=True,
                    calculation_plan_path=ROOT
                    / "configs/framework/p19_calculation_plans_v0.1.lock.json",
                    use_v24_layout_gate=True,
                    use_v25_calculation_adapter=True,
                    use_v26_handle_audit=True,
                    use_v27_partial_calculation=True,
                    use_v28_handle_role_binding=True,
                    use_v28_task_id_gate=True,
                )
                item["stage_a"] = "passed"
            except Exception as error:
                item["stage_a"] = "failed"
                item["stage_a_error"] = f"{type(error).__name__}:{error}"
                item["stage_a_failure_taxonomy"] = classify_failure(
                    stage="stage_a",
                    error_type=type(error).__name__,
                    error_message=str(error),
                    model_call_started=stage_a_dir.exists(),
                )
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
        stage_b_id = f"{task_id}-QWEN397B-v28-stage-b"
        stage_b_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_b_id
        if stage_b_dir.exists():
            raise RuntimeError(f"uncheckpointed_stage_b_requires_audit:{stage_b_dir}")
        try:
            item["stage_b_result"] = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=stage_a_dir,
                source_registry_path=ROOT / "data/manifests/p19_source_registry_v0.1.lock.json",
                slot_contracts_path=ROOT / "configs/framework/p19_slot_contracts_v0.1.lock.json",
                semantic_qualifiers_path=ROOT
                / "configs/framework/p19_semantic_qualifiers_v0.1.lock.json",
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                run_id=stage_b_id,
                use_v20_contract_gate=True,
                use_v24_preflight=True,
                use_v24_layout_gate=True,
                use_v25_single_block_ordered_spans=True,
                use_v26_atomic_projection=True,
                use_v27_handle_aliases=True,
            )
            item["stage_b"] = "passed"
        except Exception as error:
            item["stage_b"] = "failed"
            item["stage_b_error"] = f"{type(error).__name__}:{error}"
            item["stage_b_failure_taxonomy"] = classify_failure(
                stage="stage_b",
                error_type=type(error).__name__,
                error_message=str(error),
                model_call_started=stage_b_dir.exists(),
            )
        save(records)


if __name__ == "__main__":
    main()
