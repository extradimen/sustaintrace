from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p22_mineru_target_registry_v0.1.lock.json"
SOURCE_SHA = "0af4a9d19fd9d4cba72c1ec062802199873f2379f84112dc2db5dc9605ce769b"
TASKS_BY_PAGE = {
    130: ["P22-TAXONOMY-001"],
    132: ["P22-TAXONOMY-001"],
    149: ["P22-ENERGY-CALC-001"],
    151: ["P22-GHG-CALC-001"],
    171: ["P22-WATER-CALC-001"],
    172: ["P22-WATER-CALC-001"],
    203: ["P22-SAFETY-CALC-001"],
    204: ["P22-SAFETY-CALC-001"],
    374: ["P22-ASSURE-001"],
    375: ["P22-ASSURE-001"],
    377: ["P22-ASSURE-001"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    targets = []
    for page, task_ids in TASKS_BY_PAGE.items():
        recovery_generation = "RESUME01" if page in {130, 374} else "initial"
        archive = (
            "artifacts/p22/mineru_targets_RESUME01"
            if recovery_generation == "RESUME01"
            else "artifacts/p22/mineru_targets"
        )
        output = ROOT / archive / f"P22-BAYER-AR2025-p{page:04d}"
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
                "target_id": f"P22-BAYER-AR2025-p{page:04d}",
                "document_id": "P22-BAYER-AR2025",
                "document_sha256": SOURCE_SHA,
                "pdf_page": page,
                "task_ids": task_ids,
                "output_directory": str(output.relative_to(ROOT)),
                "run_record_sha256": digest(record_path),
                "recovery_generation": recovery_generation,
                "status": "success_verified",
            }
        )
    payload = {
        "schema_version": "1.0",
        "experiment_id": "P22-V31-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P22-BAYER-AR2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p22_mineru_resume_RESUME01_v0.1.lock.json"
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
