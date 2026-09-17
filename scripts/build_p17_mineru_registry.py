from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p17_mineru_target_registry_RESUME02_v0.1.json"
SOURCE_SHA = "7a7fd36bf7f274e776ef7eda30d3cda4335a99cbb45f097ae5e8268ccf7759e7"
TASKS_BY_PAGE = {
    127: ["P17-GHG-CALC-001"],
    129: ["P17-SCOPE3-BOUNDARY-001"],
    130: ["P17-SCOPE3-BOUNDARY-001"],
    141: ["P17-WATER-001"],
    142: ["P17-WATER-001"],
    172: ["P17-WORKFORCE-001"],
    178: ["P17-SAFETY-001"],
    179: ["P17-WORKFORCE-001"],
    372: ["P17-ASSURE-001"],
    373: ["P17-ASSURE-001"],
    374: ["P17-ASSURE-001"],
    375: ["P17-ASSURE-001"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    targets = []
    for page, task_ids in TASKS_BY_PAGE.items():
        generation = "RESUME02" if page == 127 else "RESUME01"
        output = (
            ROOT
            / f"artifacts/p17/mineru_targets_{generation}"
            / f"P17-BMW-GROUP-REPORT-2025-p{page:04d}"
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
                "target_id": f"P17-BMW-GROUP-REPORT-2025-p{page:04d}",
                "document_id": "P17-BMW-GROUP-REPORT-2025",
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
        "experiment_id": "P17-V26-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P17-BMW-GROUP-REPORT-2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p17_mineru_recovery_lineage_RESUME01_v0.1.lock.json",
            "data/manifests/p17_mineru_recovery_lineage_RESUME02_v0.1.lock.json",
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
