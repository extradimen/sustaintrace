from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p16_mineru_target_registry_v0.1.lock.json"
SOURCE_SHA = "82547ddb72b6b05dca88f93ed4cfe13010cb5690a5693b96721e9be3ff9c8fcc"
TASKS_BY_PAGE = {
    26: ["P16-TARGET-001"],
    30: ["P16-TARGET-001"],
    31: ["P16-TARGET-001"],
    38: ["P16-GHG-CALC-001", "P16-TARGET-001"],
    43: ["P16-POLLUTION-001"],
    44: ["P16-POLLUTION-001"],
    45: ["P16-POLLUTION-001"],
    68: ["P16-SAFETY-001"],
    90: ["P16-ACCESS-001"],
    118: ["P16-SAFETY-001"],
    129: ["P16-ASSURE-001"],
    130: ["P16-ASSURE-001"],
    131: ["P16-ASSURE-001"],
    132: ["P16-ASSURE-001"],
    133: ["P16-ASSURE-001"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    targets = []
    for page, task_ids in TASKS_BY_PAGE.items():
        output = (
            ROOT
            / "artifacts/p16/mineru_targets_RESUME01"
            / f"P16-SANOFI-SS2025-p{page:04d}"
        )
        record_path = output / "esg_rd_mineru_run.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record["returncode"] != 0 or record["input_sha256"] != SOURCE_SHA:
            raise ValueError(f"invalid_success_record:{page}")
        for item in record["output_files"]:
            path = output / item["path"]
            if not path.is_file() or digest(path) != item["sha256"]:
                raise ValueError(f"output_hash_mismatch:{page}:{item['path']}")
        targets.append(
            {
                "target_id": f"P16-SANOFI-SS2025-p{page:04d}",
                "document_id": "P16-SANOFI-SS2025",
                "document_sha256": SOURCE_SHA,
                "pdf_page": page,
                "task_ids": task_ids,
                "output_directory": str(output.relative_to(ROOT)),
                "run_record_sha256": digest(record_path),
                "recovery_generation": "RESUME01",
                "status": "success_verified",
            }
        )
    payload = {
        "schema_version": "1.0",
        "experiment_id": "P16-V25-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P16-SANOFI-SS2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p16_mineru_recovery_lineage_RESUME01_v0.1.lock.json"
        ],
        "targets": targets,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": payload["status"], "targets": len(targets)}))


if __name__ == "__main__":
    main()
