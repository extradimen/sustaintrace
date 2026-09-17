from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_b_runner import run_v13_stage_b_task

ROOT = Path(__file__).resolve().parents[1]
TASKS = [
    "P3-DEX-001",
    "P3-DEX-002",
    "P3-XPAGE-001",
    "P3-XPAGE-002",
    "P3-SCOPE-001",
    "P3-SCOPE-002",
]


def save(records: list[dict[str, object]], progress: Path, experiment: str) -> None:
    progress.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": experiment,
                "updated_at": datetime.now(UTC).isoformat(),
                "checkpoint_resume_enabled": True,
                "parent_stage_a_experiment": "V13-END-TO-END-DEVELOPMENT-DEV01",
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--generation",
        choices=["dev02", "dev03", "dev04", "dev05"],
        default="dev02",
    )
    args = parser.parse_args()
    experiment = f"V13-STAGE-B-FULL-REGRESSION-{args.generation.upper()}"
    progress = ROOT / f"data/manifests/v1.3_stage_b_full_{args.generation}_progress.json"
    records = []
    if progress.exists():
        records = json.loads(progress.read_text(encoding="utf-8"))["records"]
    completed = {item["task_id"] for item in records}
    for task_id in TASKS:
        if task_id in completed:
            continue
        run_id = f"{task_id}-QWEN397B-v13-stage-b-full-{args.generation}-r1"
        run_dir = ROOT / "research_archive" / experiment / "runs" / run_id
        if run_dir.exists():
            raise RuntimeError(f"Uncheckpointed run requires audit: {run_dir}")
        if args.generation in {"dev03", "dev04", "dev05"} and task_id == "P3-XPAGE-002":
            parent = (
                ROOT
                / "research_archive/V132-SEMANTIC-QUALIFIER-REGRESSION-DEV01/runs"
                / "P3-XPAGE-002-QWEN397B-v132-stage-a-r1"
            )
        else:
            parent = (
                ROOT
                / "research_archive/V13-END-TO-END-DEVELOPMENT-DEV01/runs"
                / f"{task_id}-QWEN397B-v13-e2e-stage-a-r1"
            )
        item: dict[str, object] = {"task_id": task_id, "retried": False}
        try:
            item["result"] = run_v13_stage_b_task(
                model_config_path=ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
                parent_run_directory=parent,
                task_pack_path=ROOT / "data/tasks/p3_task_pack_v0.1.lock.json",
                acquisition_manifest_path=(
                    ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"
                ),
                raw_root=ROOT,
                interventions_root=ROOT / "data/controlled_interventions/p3",
                registry_path=ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
                workspace_root=ROOT,
                layout_registry_path=ROOT
                / (
                    "configs/framework/"
                    + (
                        "v1.3.2_layout_fallback_development_registry.lock.json"
                        if args.generation in {"dev03", "dev04", "dev05"}
                        else "v1.3.1_layout_fallback_development_registry.lock.json"
                    )
                ),
                source_registry_path=(
                    ROOT / "data/manifests/p3_source_registry_v0.1.lock.json"
                ),
                slot_contracts_path=(
                    ROOT / "configs/framework/v1.3_p3_development_slot_contracts.json"
                ),
                semantic_qualifiers_path=(
                    ROOT / "configs/framework/v1.3.2_semantic_qualifiers.lock.json"
                    if args.generation in {"dev03", "dev04", "dev05"}
                    else None
                ),
                system_prompt_path=ROOT / "prompts/v1.3_slot_atomic_projection.txt",
                archive_root=ROOT / "research_archive",
                experiment_id=experiment,
                run_id=run_id,
                think=None,
            )
            item["status"] = "passed"
        except Exception as error:
            item["status"] = "failed"
            item["error"] = f"{type(error).__name__}:{error}"
        records.append(item)
        save(records, progress, experiment)


if __name__ == "__main__":
    main()
