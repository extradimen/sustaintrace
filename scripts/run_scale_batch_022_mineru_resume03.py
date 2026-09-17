from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import run_scale_batch_mineru_v01 as runner

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "data/results/scale_batch_022_mineru_RESUME02_summary.lock.json"
LINEAGE = ROOT / "data/manifests/scale_batch_022_mineru_RESUME03_lineage.lock.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    failed = [record for record in parent["records"] if record["status"] == "failed"]
    if LINEAGE.exists():
        raise RuntimeError("refusing to overwrite Batch 22 RESUME03 lineage")
    lineage = {
        "schema_version": "0.1",
        "resume_id": "KB-SCALE-BATCH-022-MINERU-RESUME03",
        "created_at": datetime.now(UTC).isoformat(),
        "parent_summary": str(PARENT.relative_to(ROOT)),
        "parent_summary_sha256": sha256_file(PARENT),
        "parent_failure_class": "post_processing_shutdown_recursive_mutex_failure",
        "parent_failed_pages": len(failed),
        "failed_page_keys": [
            {"document_id": item["document_id"], "page": item["page"]}
            for item in failed
        ],
        "resume_scope": "failed_pages_only",
        "successful_parent_pages_reused": parent["complete_pages"],
        "output_policy": "new_resume_directory_no_parent_overwrite",
        "cloud_transmission": False,
    }
    LINEAGE.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    runner.REGISTRY = ROOT / "data/manifests/scale_batch_022_target_pages.lock.json"
    runner.OUTPUT_ROOT = ROOT / "artifacts/scale_batch_022/mineru_targets_RESUME03"
    runner.SUMMARY = ROOT / "data/results/scale_batch_022_mineru_RESUME03_summary.lock.json"
    runner.CONFIG = ROOT / "configs/parsers/scale-batch-022-mineru-3.4.0-runtime.json"
    runner.RESUME_FROM = PARENT
    runner.BATCH_ID = "KB-SCALE-BATCH-022-MINERU-RESUME03"
    runner.main()


if __name__ == "__main__":
    main()
