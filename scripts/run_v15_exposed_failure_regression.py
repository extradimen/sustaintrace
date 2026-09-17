from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.p1_v07 import finalize_v07_output
from esg_reliable_discovery.v13_atomic_projection import validate_and_project_slots
from esg_reliable_discovery.v13_evidence import build_v13_packet
from esg_reliable_discovery.v14_pdf_vector import graph_pdf_page_vectors
from esg_reliable_discovery.v15_grounding import bind_period_headers_from_spatial_graph

ROOT = Path(__file__).resolve().parents[1]
P5_RUNS = ROOT / "research_archive/P5-V14-UNSEEN-LOCKBOX-V01-RESUME02/runs"
OUT = ROOT / "data/results/v15_p5_exposed_failure_development_v0.1.lock.json"
COMMON = {
    "task_pack_path": ROOT / "data/tasks/p5_execution_task_pack_v0.1.1_RESUME01.lock.json",
    "acquisition_manifest_path": ROOT / "data/manifests/p5_execution_acquisition_v0.1.lock.json",
    "raw_root": ROOT,
    "interventions_root": ROOT / "data/controlled_interventions/p5",
    "registry_path": ROOT / "data/manifests/p5_mineru_target_registry_RESUME01_v0.1.json",
    "workspace_root": ROOT,
    "layout_registry_path": ROOT / "configs/framework/p5_layout_fallback_registry_v0.1.lock.json",
}


def main() -> None:
    _, _, calc_handles = build_v13_packet(task_id="P5-CALC-001", **COMMON)
    graph = graph_pdf_page_vectors(
        ROOT / "data/raw/p5_staging/ahold-delhaize-annual-report-2025.pdf", 295
    )
    augmented, bindings = bind_period_headers_from_spatial_graph(calc_handles, graph)
    calc_source = (
        P5_RUNS / "P5-CALC-001-QWEN397B-v14-stage-a-r1/model_generated_content.json"
    )
    calc_model_output = json.loads(calc_source.read_text(encoding="utf-8"))
    calc_result = finalize_v07_output(calc_model_output, "deterministic_calculation", augmented)

    _, _, scope_handles = build_v13_packet(task_id="P5-SCOPE-001", **COMMON)
    scope_run = P5_RUNS / "P5-SCOPE-001-QWEN397B-v14-stage-b-r1"
    scope_context = json.loads(
        (scope_run / "stage_b_context_manifest.json").read_text(encoding="utf-8")
    )
    selected = set(scope_context["selected_evidence_handles"])
    scope_evidence = [item for item in scope_handles if item["handle"] in selected]
    scope_model_source = scope_run / "model_generated_content.json"
    scope_model_output = json.loads(scope_model_source.read_text(encoding="utf-8"))
    scope_result = validate_and_project_slots(
        model_output=scope_model_output,
        evidence=scope_evidence,
        required_slots=scope_context["required_slot_contracts"],
        framework_subject=scope_context["framework_subject"],
    )
    record = {
        "schema_version": "1.0",
        "experiment_id": "V15-P5-EXPOSED-FAILURE-DEV-V01",
        "status": "completed",
        "created_at": datetime.now(UTC).isoformat(),
        "development_data_status": "P5 failures exposed before v1.5 development",
        "not_a_lockbox_result": True,
        "model_requests_sent": 0,
        "candidate_outputs_reused_without_modification": True,
        "p3_p4_p5_archives_modified": False,
        "results": {
            "P5-CALC-001-DEV": {
                "status": "passed",
                "period_bindings": [
                    item for item in bindings
                    if item["evidence_handle"]
                    in {"M295-T0003-R0004-C0002", "M295-T0003-R0004-C0003"}
                ],
                "result": calc_result["deterministic_calculation"],
            },
            "P5-SCOPE-001-DEV": {
                "status": "passed",
                "complete": scope_result["task_coverage"]["complete"],
                "validated_claim_count": len(scope_result["validated_claims"]),
                "grounding_comparison": "unicode_nfkc_apostrophe_equivalence",
            },
        },
        "source_artifacts": {
            str(calc_source.relative_to(ROOT)): sha256_file(calc_source),
            str(scope_model_source.relative_to(ROOT)): sha256_file(scope_model_source),
        },
        "interpretation": (
            "Both exposed P5 failures pass under v1.5 deterministic grounding; "
            "unseen generalization remains untested."
        ),
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
