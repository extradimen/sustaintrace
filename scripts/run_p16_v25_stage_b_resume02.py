from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task
from esg_reliable_discovery.v20_failure_taxonomy import classify_failure

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P16-V25-UNSEEN-LOCKBOX-V01"
PROGRESS = ROOT / "data/manifests/p16_candidate_progress_RESUME02.json"
PARENT_PROGRESS = ROOT / "data/manifests/p16_candidate_progress_RESUME01.json"
TASK_PACK = ROOT / "data/tasks/p16_execution_task_pack_v0.1.lock.json"
TASK_IDS = [
    "P16-POLLUTION-001",
    "P16-SAFETY-001",
    "P16-ACCESS-001",
    "P16-ASSURE-001",
]
COMMON = {
    "model_config_path": ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
    "task_pack_path": TASK_PACK,
    "acquisition_manifest_path": ROOT / "data/manifests/p16_source_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p16",
    "registry_path": ROOT / "data/manifests/p16_mineru_target_registry_v0.1.lock.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT / "configs/framework/p16_layout_fallback_registry_v0.1.lock.json",
    "archive_root": ROOT / "research_archive",
    "experiment_id": EXPERIMENT,
    "think": None,
    "use_v15_grounding": True,
}


def save(records: list[dict[str, object]]) -> None:
    PROGRESS.write_text(
        json.dumps(
            {
                "schema_version": "2.5",
                "experiment_id": EXPERIMENT,
                "updated_at": datetime.now(UTC).isoformat(),
                "resume_id": "RESUME02",
                "parent_progress": str(PARENT_PROGRESS.relative_to(ROOT)),
                "single_attempt_per_stage": True,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> None:
    parent = json.loads(PARENT_PROGRESS.read_text())["records"]
    parent_index = {item["task_id"]: item for item in parent}
    records = json.loads(PROGRESS.read_text())["records"] if PROGRESS.exists() else []
    indexed = {item["task_id"]: item for item in records}
    for task_id in TASK_IDS:
        if parent_index[task_id].get("stage_a") != "passed":
            raise RuntimeError(f"p16_resume02_parent_stage_a_not_passed:{task_id}")
        item = indexed.get(
            task_id,
            {
                "task_id": task_id,
                "stage_a": "reused_from_RESUME01",
                "retried": False,
            },
        )
        if "stage_b" in item:
            continue
        parent_dir = (
            ROOT
            / "research_archive"
            / EXPERIMENT
            / "runs"
            / f"{task_id}-QWEN397B-v25-RESUME01-stage-a"
        )
        run_id = f"{task_id}-QWEN397B-v25-RESUME02-stage-b"
        run_dir = ROOT / "research_archive" / EXPERIMENT / "runs" / run_id
        if run_dir.exists():
            raise RuntimeError(f"uncheckpointed_stage_b_requires_audit:{run_dir}")
        try:
            item["stage_b_result"] = run_v13_stage_b_task(
                **COMMON,
                parent_run_directory=parent_dir,
                source_registry_path=ROOT / "data/manifests/p16_source_registry_v0.1.lock.json",
                slot_contracts_path=ROOT / "configs/framework/p16_slot_contracts_v0.1.lock.json",
                semantic_qualifiers_path=ROOT
                / "configs/framework/p16_semantic_qualifiers_RESUME02_v0.1.lock.json",
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                run_id=run_id,
                use_v20_contract_gate=True,
                use_v21_contract_adapters=True,
                use_v24_preflight=True,
                use_v24_layout_gate=True,
                use_v25_single_block_ordered_spans=True,
            )
            item["stage_b"] = "passed"
        except Exception as error:
            item["stage_b"] = "failed"
            item["stage_b_error"] = f"{type(error).__name__}:{error}"
            item["stage_b_failure_taxonomy"] = classify_failure(
                stage="stage_b",
                error_type=type(error).__name__,
                error_message=str(error),
                model_call_started=run_dir.exists(),
            )
        if task_id not in indexed:
            records.append(item)
            indexed[task_id] = item
        save(records)


if __name__ == "__main__":
    main()
