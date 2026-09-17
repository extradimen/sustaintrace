from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_dispatch import (
    prepare_stage_b_handle_closure_dispatch,
    restrict_projection_to_stage_a_closure,
)

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("P3-DEX-002", "P3-XPAGE-002")


def main() -> None:
    records = []
    inputs = {}
    for task_id in TASKS:
        stage_a_path = (
            ROOT
            / "research_archive/V13-END-TO-END-DEVELOPMENT-DEV01/runs"
            / f"{task_id}-QWEN397B-v13-e2e-stage-a-r1/normalized_output.json"
        )
        context_path = (
            ROOT
            / "research_archive/V13-STAGE-B-FULL-REGRESSION-DEV05/runs"
            / f"{task_id}-QWEN397B-v13-stage-b-full-dev05-r1/stage_b_context_manifest.json"
        )
        output_path = context_path.parent / "normalized_output.json"
        stage_a = json.loads(stage_a_path.read_text())
        context = json.loads(context_path.read_text())
        output = json.loads(output_path.read_text())
        records.append(
            {
                "task_id": task_id,
                "dispatch": prepare_stage_b_handle_closure_dispatch(
                    stage_a_output=stage_a,
                    stage_b_context=context,
                    projected_output=output,
                ),
                "restricted_projection": restrict_projection_to_stage_a_closure(
                    stage_a_output=stage_a,
                    stage_b_context=context,
                    projected_output=output,
                ),
            }
        )
        inputs[task_id] = {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (stage_a_path, context_path, output_path)
        }
    output = ROOT / "data/results/stage_b_handle_closure_dispatch_v0.1.lock.json"
    result = {
        "schema_version": "0.1",
        "result_id": "ESG-STAGE-B-HANDLE-CLOSURE-DISPATCH-v0.1",
        "status": "dispatch_gate_integrated_exposed_regression_complete",
        "records": records,
        "inputs": inputs,
        "model_execution_performed": False,
        "candidate_output_rewritten": False,
        "historical_output_modified": False,
        "next_gate": "add the closure gate to reusable Stage B runner entry points",
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                item["task_id"]: {
                    "dispatch": item["dispatch"]["decision"],
                    "projection": item["restricted_projection"]["status"],
                    "missing": item["restricted_projection"]["missing_slots"],
                }
                for item in records
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
