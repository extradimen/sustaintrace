from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p21_mineru_target_registry_v0.1.lock.json"
SOURCE_SHA = "6fa0a9f60a3149e585a5b52f06efde1e0aaa5d1156da0d71a1fd40822df7f8b7"
TASKS_BY_PAGE = {
    192: ["P21-ENERGY-001"],
    194: ["P21-GHG-CALC-001", "P21-SCOPE3-001"],
    195: ["P21-GHG-CALC-001", "P21-SCOPE3-001"],
    242: ["P21-TAXONOMY-001"],
    245: ["P21-TAXONOMY-001"],
    262: ["P21-WORKFORCE-001"],
    263: ["P21-WORKFORCE-001"],
    433: ["P21-ASSURE-001"],
    434: ["P21-ASSURE-001"],
    436: ["P21-ASSURE-001"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    targets = []
    for page, task_ids in TASKS_BY_PAGE.items():
        recovery_generation = "RESUME01" if page in {192, 433} else "initial"
        archive = (
            "artifacts/p21/mineru_targets_RESUME01"
            if recovery_generation == "RESUME01"
            else "artifacts/p21/mineru_targets"
        )
        output = ROOT / archive / f"P21-BASF-AR2025-p{page:04d}"
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
                "target_id": f"P21-BASF-AR2025-p{page:04d}",
                "document_id": "P21-BASF-AR2025",
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
        "experiment_id": "P21-V30-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P21-BASF-AR2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p21_mineru_resume_RESUME01_v0.1.lock.json"
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
