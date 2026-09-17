from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task
from esg_reliable_discovery.v20_failure_taxonomy import classify_failure

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P17-V26-UNSEEN-LOCKBOX-V01"
RESUME_ID = os.environ.get("P17_RESUME_ID", "").strip()
PROGRESS = ROOT / (
    f"data/manifests/p17_candidate_progress_{RESUME_ID}.json"
    if RESUME_ID
    else "data/manifests/p17_candidate_progress.json"
)
TASK_PACK = ROOT / "data/tasks/p17_execution_task_pack_v0.1.lock.json"
RELEASE = ROOT / "data/tasks/p17_execution_release_RESUME02_v0.2.lock.json"
STAGE_B_TYPES = {
    "direct_extraction",
    "scope_subject_boundary",
    "cross_page_relation",
}
EXPECTED_PAGES = [127, 129, 130, 141, 142, 172, 178, 179, 372, 373, 374, 375]
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": ROOT
    / "data/manifests/p17_source_acquisition_RESUME01_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p17",
    "registry_path": ROOT
    / "data/manifests/p17_mineru_target_registry_RESUME02_v0.1.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT
    / "configs/framework/p17_layout_fallback_registry_RESUME02_v0.1.lock.json",
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
    "use_v15_grounding": True,
}


def save(records: list[dict[str, object]]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "2.6",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "single_attempt_per_stage": True,
                "reference_loaded_by_orchestrator": False,
                "parent_progress": (
                    "data/manifests/p17_candidate_progress.json" if RESUME_ID else None
                ),
                "resume_id": RESUME_ID or None,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    pack = json.loads(TASK_PACK.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    if not release.get("inference_allowed"):
        raise RuntimeError("p17_task_pack_not_released")
    authorization = json.loads(
        (ROOT / release["exact_authorization_record"]).read_text()
    )
    if authorization.get("status") != "authorized_by_user":
        raise RuntimeError("p17_cloud_authorization_invalid")
    if (
        authorization.get("pages") != EXPECTED_PAGES
        or authorization.get("model") != "qwen3.5:397b-cloud"
    ):
        raise RuntimeError("p17_cloud_authorization_scope_mismatch")
    readiness = json.loads(
        (
            ROOT
            / "data/results/p17_v26_local_readiness_RESUME03_v0.1.lock.json"
        ).read_text()
    )
    expected = "local_readiness_passed_waiting_for_explicit_cloud_authorization"
    if readiness.get("status") != expected:
        raise RuntimeError("p17_prefreeze_audit_not_passed")

    records = json.loads(PROGRESS.read_text())["records"] if PROGRESS.exists() else []
    indexed = {item["task_id"]: item for item in records}
    for task in pack["tasks"]:
        task_id = task["task_id"]
        item = indexed.get(
            task_id,
            {"task_id": task_id, "task_type": task["task_type"], "retried": False},
        )
        resume_label = f"-{RESUME_ID}" if RESUME_ID else ""
        stage_a_id = f"{task_id}-QWEN397B-v26{resume_label}-stage-a"
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
                    / "configs/framework/"
                    "p17_calculation_plans_RESUME03_v0.1.lock.json",
                    use_v24_layout_gate=True,
                    use_v26_calculation_adapter=True,
                    use_v26_handle_audit=True,
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
        stage_b_id = f"{task_id}-QWEN397B-v26{resume_label}-stage-b"
        stage_b_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / stage_b_id
        if stage_b_dir.exists():
            raise RuntimeError(f"uncheckpointed_stage_b_requires_audit:{stage_b_dir}")
        try:
            item["stage_b_result"] = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=stage_a_dir,
                source_registry_path=ROOT
                / "data/manifests/p17_source_registry_RESUME01_v0.1.lock.json",
                slot_contracts_path=ROOT
                / "configs/framework/p17_slot_contracts_RESUME02_v0.1.lock.json",
                semantic_qualifiers_path=ROOT
                / "configs/framework/p17_semantic_qualifiers_RESUME02_v0.1.lock.json",
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                run_id=stage_b_id,
                use_v20_contract_gate=True,
                use_v21_contract_adapters=False,
                use_v24_preflight=True,
                use_v24_layout_gate=True,
                use_v26_atomic_projection=True,
                use_v26_semantic_single_block_spans=True,
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
