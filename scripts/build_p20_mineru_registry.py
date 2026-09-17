from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p20_mineru_target_registry_RESUME01_v0.1.lock.json"
SOURCE_SHA = "55b975cd13fc361638ed13bf32856a2629e46e88bdfc6ad9208bd8807992a599"
TASKS_BY_PAGE = {
    85: ["P20-ENERGY-001"],
    86: ["P20-GHG-CALC-001"],
    87: ["P20-GHG-CALC-001", "P20-SCOPE3-001"],
    111: ["P20-TAXONOMY-001"],
    112: ["P20-TAXONOMY-001"],
    113: ["P20-TAXONOMY-001"],
    114: ["P20-TAXONOMY-001"],
    120: ["P20-WORKFORCE-001"],
    121: ["P20-WORKFORCE-001"],
    134: ["P20-ASSURE-001"],
    135: ["P20-ASSURE-001"],
    136: ["P20-ASSURE-001"],
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
            / "artifacts/p20/mineru_targets_RESUME01"
            / f"P20-HOLCIM-SS2025-p{page:04d}"
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
                "target_id": f"P20-HOLCIM-SS2025-p{page:04d}",
                "document_id": "P20-HOLCIM-SS2025",
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
        "experiment_id": "P20-V29-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P20-HOLCIM-SS2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p20_mineru_resume_RESUME01_v0.1.lock.json"
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
