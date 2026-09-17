from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums
from esg_reliable_discovery.v15_evidence import build_v15_packet
from esg_reliable_discovery.v21_contract_adapters import validate_and_project_slots_v21
from esg_reliable_discovery.v23_preflight import execute_calculation_plan_v23
from esg_reliable_discovery.v25_integrity import (
    execute_calculation_plan_v25,
    normalize_calculation_binding_v25,
    select_single_block_ordered_spans_v25,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P15-V24-UNSEEN-LOCKBOX-V01"
OUTPUT = (
    ROOT
    / "data/results/v2.5_p15_exposed_failure_regression_RESUME02_v0.1.lock.json"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packet(task_id: str) -> list[dict[str, object]]:
    _, _, evidence = build_v15_packet(
        task_pack_path=ROOT / "data/tasks/p15_execution_task_pack_v0.1.lock.json",
        task_id=task_id,
        acquisition_manifest_path=ROOT
        / "data/manifests/p15_source_acquisition_v0.1.lock.json",
        raw_root=ROOT,
        interventions_root=ROOT / "data/controlled_interventions/p15",
        registry_path=ROOT
        / "data/manifests/p15_mineru_target_registry_RESUME03_v0.1.json",
        workspace_root=ROOT,
        layout_registry_path=ROOT
        / "configs/framework/p15_layout_fallback_registry_v0.1.lock.json",
    )
    return evidence


def selected_evidence(task_id: str) -> list[dict[str, object]]:
    stage_a = (
        ROOT
        / "research_archive"
        / EXPERIMENT
        / "runs"
        / f"{task_id}-QWEN397B-v24-RESUME01-stage-a"
    )
    normalized = json.loads((stage_a / "normalized_output.json").read_text())
    selected = {item["source_handle"] for item in normalized["resolved_evidence"]}
    return [item for item in packet(task_id) if item["handle"] in selected]


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    runs = ROOT / "research_archive" / EXPERIMENT / "runs"
    contracts_path = ROOT / "configs/framework/p15_slot_contracts_v0.1.lock.json"
    contracts = json.loads(contracts_path.read_text())["contracts"]

    ghg_archive = runs / "P15-GHG-CALC-001-QWEN397B-v24-RESUME01-stage-a"
    verify_run_checksums(ghg_archive)
    ghg_model = json.loads((ghg_archive / "model_generated_content.json").read_text())
    plans_path = ROOT / "configs/framework/p15_calculation_plans_v0.1.lock.json"
    plan = json.loads(plans_path.read_text())["plans"]["P15-GHG-CALC-001"]
    binding, binding_audit = normalize_calculation_binding_v25(ghg_model, plan)
    ghg_evidence = packet("P15-GHG-CALC-001")
    legacy = execute_calculation_plan_v23(binding, ghg_evidence, plan)
    calculation = execute_calculation_plan_v25(binding, ghg_evidence, plan)

    stage_b = {}
    for task_id in ("P15-WATER-QUALITY-001", "P15-SAFETY-001", "P15-ASSURE-001"):
        archive = runs / f"{task_id}-QWEN397B-v24-RESUME01-stage-b"
        verify_run_checksums(archive)
        model_output = json.loads((archive / "model_generated_content.json").read_text())
        evidence = selected_evidence(task_id)
        selected_contracts, selection_audit = select_single_block_ordered_spans_v25(
            contracts[task_id], evidence
        )
        projected = validate_and_project_slots_v21(
            model_output=model_output,
            evidence=evidence,
            required_slots=selected_contracts,
            framework_subject={
                "entity_id": "ENTITY::P15-NOVARTIS-NFM2025",
                "entity_label": "Novartis AG",
            },
        )
        stage_b[task_id] = {
            "status": "passed",
            "validated_claim_count": len(projected["validated_claims"]),
            "contract_selection": selection_audit,
        }

    payload = {
        "schema_version": "2.5",
        "status": "passed",
        "development_set": "P15 exposed failures only",
        "candidate_model_called": False,
        "p15_modified_rerun_or_rescored": False,
        "ghg_calculation_regression": {
            "binding_audit": binding_audit,
            "legacy_binary_float_total": legacy["values"]["calculated_total"],
            "v25_values": calculation["values"],
            "numeric_method": calculation["numeric_method"],
            "passed": calculation["values"]["calculated_total"] == 4377.1
            and calculation["values"]["difference"] == 0.0,
        },
        "stage_b_regressions": stage_b,
        "inputs": {
            "slot_contracts": str(contracts_path.relative_to(ROOT)),
            "slot_contracts_sha256": digest(contracts_path),
            "calculation_plans": str(plans_path.relative_to(ROOT)),
            "calculation_plans_sha256": digest(plans_path),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"status": payload["status"], "stage_b": list(stage_b)}))


if __name__ == "__main__":
    main()
