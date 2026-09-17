from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.evidence_contract_validation import (
    validate_stage_b_projection_lineage,
)
from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("P3-DEX-002", "P3-XPAGE-002")


def main() -> None:
    records = []
    artifact_hashes = {}
    for task_id in TASKS:
        stage_a_dir = (
            ROOT
            / "research_archive/V13-END-TO-END-DEVELOPMENT-DEV01/runs"
            / f"{task_id}-QWEN397B-v13-e2e-stage-a-r1"
        )
        stage_b_dir = (
            ROOT
            / "research_archive/V13-STAGE-B-FULL-REGRESSION-DEV05/runs"
            / f"{task_id}-QWEN397B-v13-stage-b-full-dev05-r1"
        )
        paths = {
            "stage_a": stage_a_dir / "normalized_output.json",
            "stage_b_context": stage_b_dir / "stage_b_context_manifest.json",
            "projected_output": stage_b_dir / "normalized_output.json",
            "projection_validation": stage_b_dir / "validation.json",
        }
        record = validate_stage_b_projection_lineage(
            task_id=task_id,
            stage_a=json.loads(paths["stage_a"].read_text()),
            stage_b_context=json.loads(paths["stage_b_context"].read_text()),
            projected_output=json.loads(paths["projected_output"].read_text()),
            projection_validation=json.loads(paths["projection_validation"].read_text()),
        )
        records.append(record)
        artifact_hashes[task_id] = {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in paths.items()
        }
    output_path = ROOT / "data/knowledge_bases/v0.1/stage_b_projection_lineage_validations.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    result = {
        "schema_version": "0.1",
        "result_id": "ESG-STAGE-B-PROJECTION-REPAIR-LINEAGE-v0.1",
        "status": "existing_v13_development_lineage_validated_for_controller_reuse",
        "tasks": list(TASKS),
        "validated": sum(item["status"] == "validated_development_lineage" for item in records),
        "current_phase_execution_performed": False,
        "historical_outputs_modified": False,
        "reference_used_as_candidate_input": False,
        "artifact_hashes": artifact_hashes,
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "bind validated projection lineage as supervised executor candidate",
    }
    result_path = ROOT / "data/results/stage_b_projection_repair_lineage_v0.1.lock.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"validated": result["validated"], "tasks": result["tasks"]}))


if __name__ == "__main__":
    main()
