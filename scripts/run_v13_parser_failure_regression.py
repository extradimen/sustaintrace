from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task

ROOT = Path(__file__).resolve().parents[1]
TASKS = ["P3-DEX-001", "P3-CALC-001"]


def save(
    records: list[dict[str, object]], progress: Path, experiment: str
) -> None:
    progress.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "experiment_id": experiment,
                "updated_at": datetime.now(UTC).isoformat(),
                "development_data_only": True,
                "p3_rerun": False,
                "checkpoint_resume_enabled": True,
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
    parser.add_argument("--generation", choices=["dev01", "dev02"], default="dev01")
    args = parser.parse_args()
    experiment = f"V13-PARSER-FAILURE-REGRESSION-{args.generation.upper()}"
    progress = ROOT / (
        f"data/manifests/v1.3_parser_failure_regression_{args.generation}_progress.json"
    )
    records = []
    if progress.exists():
        records = json.loads(progress.read_text(encoding="utf-8"))["records"]
    completed = {item["task_id"] for item in records}
    for task_id in TASKS:
        if task_id in completed:
            continue
        run_id = f"{task_id}-QWEN397B-v13-{args.generation}-stage-a-r1"
        run_dir = ROOT / "research_archive" / experiment / "runs" / run_id
        if run_dir.exists():
            raise RuntimeError(f"Uncheckpointed existing run requires audit: {run_dir}")
        item: dict[str, object] = {"task_id": task_id, "retried": False}
        try:
            item["result"] = run_v13_stage_a_task(
                model_config_path=ROOT / "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
                task_pack_path=ROOT / "data/tasks/p3_task_pack_v0.1.lock.json",
                task_id=task_id,
                acquisition_manifest_path=(
                    ROOT / "data/manifests/p3_execution_acquisition_v0.1.lock.json"
                ),
                raw_root=ROOT,
                interventions_root=ROOT / "data/controlled_interventions/p3",
                registry_path=ROOT / "data/manifests/p3_mineru_target_registry_v0.1.json",
                workspace_root=ROOT,
                layout_registry_path=(
                    ROOT / "configs/framework/v1.3_layout_fallback_development_registry.json"
                ),
                system_prompt_path=ROOT / "prompts/v1.0_evidence_reasoning.txt",
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
