from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p19_mineru_target_registry_v0.1.lock.json"
SOURCE_SHA = "f5475f1e043eaa99526772c0e06677a74ab2c2abb8181755afbe02a10e395092"
TASKS_BY_PAGE = {
    58: ["P19-WORKFORCE-001"],
    65: ["P19-ENERGY-001"],
    66: ["P19-GHG-CALC-001", "P19-SCOPE3-001"],
    80: ["P19-TAXONOMY-001"],
    123: ["P19-ASSURE-001"],
    124: ["P19-ASSURE-001"],
    135: ["P19-TAXONOMY-001"],
    136: ["P19-TAXONOMY-001"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    targets = []
    for page, task_ids in TASKS_BY_PAGE.items():
        generation = "RESUME02" if page == 65 else "RESUME01"
        output = (
            ROOT
            / f"artifacts/p19/mineru_targets_{generation}"
            / f"P19-NOVO-NORDISK-AR2025-p{page:04d}"
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
                "target_id": f"P19-NOVO-NORDISK-AR2025-p{page:04d}",
                "document_id": "P19-NOVO-NORDISK-AR2025",
                "document_sha256": SOURCE_SHA,
                "pdf_page": page,
                "task_ids": task_ids,
                "output_directory": str(output.relative_to(ROOT)),
                "run_record_sha256": digest(record_path),
                "recovery_generation": generation,
                "status": "success_verified",
            }
        )
    payload = {
        "schema_version": "1.0",
        "experiment_id": "P19-V28-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P19-NOVO-NORDISK-AR2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p19_mineru_recovery_lineage_RESUME01_v0.1.lock.json",
            "data/manifests/p19_mineru_recovery_lineage_RESUME02_v0.1.lock.json"
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
