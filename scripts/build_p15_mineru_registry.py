from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/p15_mineru_target_registry_RESUME03_v0.1.json"
SOURCE_SHA = "8dbc7f74b114b52eafa7a454bd0cbe49efae3a8ea61e931f7eb075d39336758b"
TASKS_BY_PAGE = {
    20: ["P15-TARGET-001"],
    21: ["P15-TARGET-001"],
    22: ["P15-TARGET-001"],
    27: ["P15-GHG-CALC-001"],
    28: ["P15-GHG-CALC-001"],
    29: ["P15-WATER-QUALITY-001"],
    30: ["P15-WATER-QUALITY-001"],
    31: ["P15-SAFETY-001"],
    32: ["P15-SAFETY-001"],
    36: ["P15-ACCESS-001"],
    43: ["P15-ASSURE-001"],
    44: ["P15-ASSURE-001"],
    45: ["P15-ASSURE-001"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    targets = []
    for page, task_ids in TASKS_BY_PAGE.items():
        resume = "RESUME03" if page in {31, 36} else "RESUME02"
        output = (
            ROOT
            / f"artifacts/p15/mineru_targets_{resume}"
            / f"P15-NOVARTIS-NFM2025-p{page:04d}"
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
                "target_id": f"P15-NOVARTIS-NFM2025-p{page:04d}",
                "document_id": "P15-NOVARTIS-NFM2025",
                "document_sha256": SOURCE_SHA,
                "pdf_page": page,
                "task_ids": task_ids,
                "output_directory": str(output.relative_to(ROOT)),
                "run_record_sha256": digest(record_path),
                "recovery_generation": resume,
                "status": "success_verified",
            }
        )
    payload = {
        "schema_version": "1.0",
        "experiment_id": "P15-V24-UNSEEN-LOCKBOX-V01",
        "status": "all_target_pages_successfully_parsed_and_hash_verified",
        "document_id": "P15-NOVARTIS-NFM2025",
        "document_sha256": SOURCE_SHA,
        "target_count": len(targets),
        "success_count": len(targets),
        "failure_count": 0,
        "recovery_lineage": [
            "data/manifests/p15_mineru_recovery_lineage_RESUME01_v0.1.lock.json",
            "data/manifests/p15_mineru_recovery_lineage_RESUME02_v0.1.lock.json",
            "data/manifests/p15_mineru_recovery_lineage_RESUME03_v0.1.lock.json",
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
