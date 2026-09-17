from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal
from pathlib import Path

from esg_reliable_discovery.v24_integrity import (
    dry_run_stage_b_contracts_v24,
    validate_layout_registry_v24,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/results/p15_v24_prefreeze_integrity_audit_RESUME01_v0.1.lock.json"
FREEZE = ROOT / "data/manifests/p15_simulated_reference_and_contract_freeze_v0.1.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


def main() -> None:
    for output in (OUT, FREEZE):
        if output.exists():
            raise RuntimeError(f"refusing_to_overwrite:{output}")

    tasks_path = ROOT / "data/tasks/p15_task_pack_v0.1.lock.json"
    contracts_path = ROOT / "configs/framework/p15_slot_contracts_v0.1.lock.json"
    layout_path = ROOT / "configs/framework/p15_layout_fallback_registry_v0.1.lock.json"
    registry_path = ROOT / "data/manifests/p15_mineru_target_registry_RESUME03_v0.1.json"
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))["contracts"]
    layout = json.loads(layout_path.read_text(encoding="utf-8"))["targets"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))["targets"]

    page_text: dict[int, str] = {}
    for record in registry:
        out = ROOT / record["output_directory"]
        markdowns = list(out.rglob("*.md"))
        contents = list(out.rglob("*_content_list.json"))
        if len(markdowns) != 1 or len(contents) != 1:
            raise RuntimeError(f"unexpected_parser_outputs:{record['pdf_page']}")
        page_text[record["pdf_page"]] = normalized(
            markdowns[0].read_text(encoding="utf-8")
            + "\n"
            + contents[0].read_text(encoding="utf-8")
        )

    quote_failures = []
    key_failures = []
    quote_count = 0
    refs = []
    for task in tasks:
        ref_path = ROOT / f"data/annotations/p15_simulated/{task['task_id']}.json"
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        refs.append(ref_path)
        ref_keys = set(ref["normalized_value"])
        contract_keys = {item["slot_id"] for item in contracts[task["task_id"]]}
        if ref_keys != contract_keys:
            key_failures.append(
                {
                    "task_id": task["task_id"],
                    "reference_only": sorted(ref_keys - contract_keys),
                    "contract_only": sorted(contract_keys - ref_keys),
                }
            )
        allowed = set(task["target_pages"])
        for evidence in ref["evidence"]:
            quote_count += 1
            page = evidence["pdf_page"]
            quote = normalized(evidence["quote"])
            if page not in allowed or quote not in page_text.get(page, ""):
                quote_failures.append(
                    {"task_id": task["task_id"], "pdf_page": page, "quote": evidence["quote"]}
                )

    layout_gate = validate_layout_registry_v24(layout)
    preflights = {
        task_id: dry_run_stage_b_contracts_v24(task_contracts)
        for task_id, task_contracts in contracts.items()
    }
    slot_count = sum(len(items) for items in contracts.values())
    calculation_decimal = Decimal("192.3") + Decimal("14.9") + Decimal("4169.9")
    reported_decimal = Decimal("4377.1")
    calculation = float(calculation_decimal)
    passed = (
        not quote_failures
        and not key_failures
        and calculation_decimal == reported_decimal
        and all(result["status"] == "passed" for result in preflights.values())
    )
    audit = {
        "schema_version": "2.4",
        "experiment_id": "P15-V24-UNSEEN-LOCKBOX-V01",
        "status": "passed" if passed else "failed",
        "candidate_model_called": False,
        "cloud_transmission_count": 0,
        "task_count": len(tasks),
        "slot_count": slot_count,
        "mineru_pages_verified": len(page_text),
        "layout_gate": layout_gate,
        "evidence_quote_audit": {
            "quotes_checked": quote_count,
            "failures": quote_failures,
        },
        "reference_contract_key_audit": {
            "tasks_checked": len(tasks),
            "failures": key_failures,
        },
        "stage_b_contract_preflights": preflights,
        "deterministic_calculation": {
            "expression": "192.3 + 14.9 + 4169.9",
            "calculated": calculation,
            "reported": float(reported_decimal),
            "difference": float(calculation_decimal - reported_decimal),
            "numeric_method": "decimal fixed-point from source literals",
            "passed": calculation_decimal == reported_decimal,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not passed:
        raise RuntimeError(json.dumps(audit, ensure_ascii=False))

    artifacts = refs + [
        contracts_path,
        ROOT / "configs/framework/p15_calculation_plans_v0.1.lock.json",
        ROOT / "configs/framework/p15_semantic_qualifiers_v0.1.lock.json",
        ROOT / "configs/framework/p15_two_dimensional_table_graph_v0.1.lock.json",
        OUT,
    ]
    freeze = {
        "schema_version": "1.0",
        "experiment_id": "P15-V24-UNSEEN-LOCKBOX-V01",
        "status": (
            "simulated_references_contracts_calculation_and_table_graph_"
            "frozen_before_candidate_inference"
        ),
        "frozen_at_local_date": "2026-09-09",
        "reference_type": "codex_gpt_simulated_expert_not_independent_human_gold",
        "candidate_model_used_for_reference_creation": False,
        "cloud_transmission_count": 0,
        "task_count": len(tasks),
        "slot_count": slot_count,
        "prefreeze_audit": str(OUT.relative_to(ROOT)),
        "prefreeze_audit_sha256": digest(OUT),
        "artifacts": [
            {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
            for path in sorted(artifacts)
        ],
        "immutability": {
            "candidate_inference_started": False,
            "post_candidate_reference_edits_allowed": False,
            "p3_through_p14_modified": False,
        },
    }
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    FREEZE.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "tasks": len(tasks),
                "slots": slot_count,
                "quotes": quote_count,
            }
        )
    )


if __name__ == "__main__":
    main()
