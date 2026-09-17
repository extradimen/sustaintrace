from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "data/manifests/heterogeneous_component_validation_v0.1.lock.json"
OUTPUT = ROOT / (
    "data/manifests/heterogeneous_component_validation_RESUME01_v0.1.lock.json"
)
PARENT_SHA256 = "5640704321fb63fe1e045519ae47c3322c3d1ba2c18b3299d5926d4012a8c865"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_heterogeneous_resume01_manifest")
    if sha256_file(PARENT) != PARENT_SHA256:
        raise ValueError("parent_manifest_hash_mismatch")
    manifest = json.loads(PARENT.read_text())
    manifest["status"] = "frozen_not_executed"
    manifest["resume_lineage"] = {
        "parent": str(PARENT.relative_to(ROOT)),
        "parent_sha256": PARENT_SHA256,
        "parent_execution_performed": False,
        "reason": (
            "freeze-time source-label audit found that the Shell row includes "
            "the literal footnote marker [C]"
        ),
        "changed_fields": [
            "HET-CALC-POS-SHELL-001.adapter_inputs.input_cells[*].row"
        ],
    }
    for case in manifest["cases"]:
        if case["case_id"] == "HET-CALC-POS-SHELL-001":
            for cell in case["adapter_inputs"]["input_cells"]:
                cell["row"] = "Gross Scope 1 GHG emissions [C]"
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(sha256_file(OUTPUT))


if __name__ == "__main__":
    main()
