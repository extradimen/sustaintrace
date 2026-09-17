from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.v15_evidence import build_v15_packet
from esg_reliable_discovery.v16_comparison import (
    compose_reported_and_recalculated_comparison,
)
from esg_reliable_discovery.v16_conflict import classify_scope_conflict_and_causality

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "research_archive/P6-V15-UNSEEN-LOCKBOX-V01/runs"
OUT = ROOT / "data/results/v16_p6_exposed_failure_development_v0.1.lock.json"
COMMON = {
    "task_pack_path": ROOT / "data/tasks/p6_execution_task_pack_v0.1.lock.json",
    "acquisition_manifest_path": ROOT / "data/manifests/p6_source_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p6",
    "registry_path": ROOT / "data/manifests/p6_mineru_target_registry_RESUME02_v0.1.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT / "configs/framework/p6_layout_fallback_registry_v0.1.lock.json",
}


def main() -> None:
    _, _, calc_handles = build_v15_packet(task_id="P6-CALC-001", **COMMON)
    calc_path = RUNS / "P6-CALC-001-QWEN397B-v15-stage-a-r1/normalized_output.json"
    calc = json.loads(calc_path.read_text(encoding="utf-8"))
    comparison = compose_reported_and_recalculated_comparison(
        deterministic_calculation=calc["deterministic_calculation"],
        reported_observation={
            "value": 12,
            "direction": "decrease",
            "evidence_handle": "M235-T0009-R0002",
        },
        available_handles=calc_handles,
    )

    conflict_a = RUNS / "P6-CONFLICT-001-QWEN397B-v15-stage-a-r1/normalized_output.json"
    conflict_b = RUNS / "P6-CONFLICT-001-QWEN397B-v15-stage-b-r1/normalized_output.json"
    stage_a = json.loads(conflict_a.read_text(encoding="utf-8"))
    stage_b = json.loads(conflict_b.read_text(encoding="utf-8"))
    claims = {item["slot_id"]: item for item in stage_b["validated_claims"]}
    evidence = [
        {
            "handle": item["source_handle"],
            "verbatim_text": item["verbatim_excerpt"],
        }
        for item in stage_a["resolved_evidence"]
    ]
    conflict = classify_scope_conflict_and_causality(
        left_observation=claims["unilever_fatality_reported"],
        right_observation=claims["ice_cream_fatality_reported"],
        proposed_causal_explanation=(
            "because the fatality was a contractor (other worker), not an Unilever employee"
        ),
        evidence=evidence,
    )
    result = {
        "schema_version": "1.0",
        "experiment_id": "V16-P6-EXPOSED-FAILURE-DEV-V01",
        "status": "completed",
        "created_at": datetime.now(UTC).isoformat(),
        "not_a_lockbox_result": True,
        "model_requests_sent": 0,
        "candidate_outputs_reused_without_modification": True,
        "p3_p4_p5_p6_archives_modified": False,
        "results": {
            "P6-CALC-001-DEV": comparison,
            "P6-CONFLICT-001-DEV": conflict,
        },
        "source_artifacts": {
            str(calc_path.relative_to(ROOT)): sha256_file(calc_path),
            str(conflict_a.relative_to(ROOT)): sha256_file(conflict_a),
            str(conflict_b.relative_to(ROOT)): sha256_file(conflict_b),
        },
        "interpretation": (
            "Both exposed P6 limitations are now represented deterministically; "
            "unseen generalization remains untested."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
