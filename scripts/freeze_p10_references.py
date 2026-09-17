from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    references = {
        task_id: digest(f"data/annotations/p10_simulated/{task_id}.json")
        for task_id in (
            "P10-ASSURE-001",
            "P10-BOUNDARY-001",
            "P10-CALC-001",
            "P10-SAFETY-001",
            "P10-SCOPE3-001",
            "P10-TARGET-001",
        )
    }
    manifest = {
        "schema_version": "1.0",
        "experiment_id": "P10-V19-UNSEEN-LOCKBOX-V01",
        "status": (
            "simulated_references_frozen_after_questions_and_integrity_audit_"
            "before_candidate_inference"
        ),
        "reference_author": "codex_gpt_simulated_expert",
        "human_gold_claimed": False,
        "candidate_model_excluded": True,
        "task_pack_sha256": digest("data/tasks/p10_task_pack_v0.1.lock.json"),
        "slot_contracts_sha256": digest("configs/framework/p10_slot_contracts_v0.1.lock.json"),
        "parser_registry_sha256": digest(
            "data/manifests/p10_mineru_target_registry_RESUME03_v0.1.lock.json"
        ),
        "table_graph_sha256": digest(
            "configs/framework/p10_two_dimensional_table_graph_v0.1.lock.json"
        ),
        "prefreeze_audit_sha256": digest(
            "data/results/p10_v19_prefreeze_integrity_audit_v0.1.lock.json"
        ),
        "references": references,
        "audit_notes": [
            "All six references passed the mandatory v1.9 page-window, "
            "quote-grounding and required-field gate.",
            "The page 426 versus page 427 assurance-range discrepancy is an "
            "explicit controlled conflict, not silently reconciled.",
            "The page 360 image-dominant target table uses the frozen "
            "native-layout two-dimensional graph.",
        ],
    }
    output = ROOT / "data/manifests/p10_simulated_reference_freeze_v0.1.lock.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
