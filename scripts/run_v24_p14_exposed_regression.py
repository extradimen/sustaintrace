from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums
from esg_reliable_discovery.v13_evidence import build_v13_packet
from esg_reliable_discovery.v23_preflight import execute_calculation_plan_v23
from esg_reliable_discovery.v24_integrity import (
    dry_run_stage_b_contracts_v24,
    normalize_calculation_binding_v24,
    validate_layout_registry_v24,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/v2.4_p14_exposed_failure_regression_v0.1.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    archive = (
        ROOT
        / "research_archive/P14-V23-UNSEEN-LOCKBOX-V01/runs"
        / "P14-GHG-CALC-001-QWEN397B-v23-RESUME01-stage-a"
    )
    verify_run_checksums(archive)
    raw_model_output = json.loads(
        (archive / "model_generated_content.json").read_text(encoding="utf-8")
    )
    _, _, evidence = build_v13_packet(
        task_pack_path=ROOT / "data/tasks/p14_execution_task_pack_v0.1.lock.json",
        task_id="P14-GHG-CALC-001",
        acquisition_manifest_path=ROOT
        / "data/manifests/p14_source_acquisition_v0.1.lock.json",
        raw_root=ROOT,
        interventions_root=ROOT / "data/controlled_interventions/p14",
        registry_path=ROOT
        / "data/manifests/p14_mineru_target_registry_RESUME04_v0.1.json",
        workspace_root=ROOT,
        layout_registry_path=ROOT
        / "configs/framework/p14_layout_fallback_registry_RESUME01_v0.1.lock.json",
    )
    plans_path = ROOT / "configs/framework/p14_calculation_plans_v0.1.lock.json"
    plan = json.loads(plans_path.read_text(encoding="utf-8"))["plans"][
        "P14-GHG-CALC-001"
    ]
    binding, adapter_audit = normalize_calculation_binding_v24(raw_model_output, plan)
    calculation = execute_calculation_plan_v23(binding, evidence, plan)

    contracts_path = ROOT / "configs/framework/p14_slot_contracts_v0.1.lock.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))["contracts"]
    span_preflights = {
        task_id: dry_run_stage_b_contracts_v24(contracts[task_id])
        for task_id in ("P14-SLB-001", "P14-ASSURE-001")
    }
    layout_path = (
        ROOT
        / "configs/framework/p14_layout_fallback_registry_RESUME01_v0.1.lock.json"
    )
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout_gate = validate_layout_registry_v24(layout["targets"])

    payload = {
        "schema_version": "2.4",
        "status": "passed",
        "development_set": "P14 exposed failures only",
        "candidate_model_called": False,
        "hidden_or_unseen_report_used": False,
        "p14_modified_or_rerun": False,
        "calculation_binding_regression": {
            "source_archive": str(archive.relative_to(ROOT)),
            "source_archive_verified": True,
            "adapter_audit": adapter_audit,
            "framework_values": calculation["values"],
            "expected_exposed_values": {
                "calculated_total": 6421686.0,
                "difference": 0.0,
            },
            "passed": calculation["values"]["calculated_total"] == 6421686
            and calculation["values"]["difference"] == 0,
        },
        "ordered_span_preflight_regression": span_preflights,
        "layout_registry_gate_regression": layout_gate,
        "inputs": {
            "calculation_plan": str(plans_path.relative_to(ROOT)),
            "calculation_plan_sha256": digest(plans_path),
            "slot_contracts": str(contracts_path.relative_to(ROOT)),
            "slot_contracts_sha256": digest(contracts_path),
            "layout_registry": str(layout_path.relative_to(ROOT)),
            "layout_registry_sha256": digest(layout_path),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": payload["status"], "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
