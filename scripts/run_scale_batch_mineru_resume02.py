from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import run_scale_batch_mineru_v01 as runner

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "data/results/scale_batch_001_mineru_RESUME01_summary.lock.json"
LINEAGE = ROOT / "data/manifests/scale_batch_001_mineru_RESUME02_lineage.lock.json"


def main() -> None:
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    failed = [record for record in parent["records"] if record["status"] == "failed"]
    if len(failed) != 1:
        raise RuntimeError(f"expected_one_failed_parent_page:{len(failed)}")
    lineage = {
        "schema_version": "0.1",
        "resume_id": "KB-SCALE-BATCH-001-MINERU-RESUME02",
        "created_at": datetime.now(UTC).isoformat(),
        "parent_summary": str(PARENT.relative_to(ROOT)),
        "parent_summary_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(),
        "parent_failure_class": "post_processing_runtime_shutdown_abort",
        "parent_failed_pages": 1,
        "resume_scope": "failed_page_only",
        "successful_parent_pages_reused": parent["complete_pages"],
        "cloud_transmission": False,
    }
    LINEAGE.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    runner.OUTPUT_ROOT = ROOT / "artifacts/scale_batch_001/mineru_targets_RESUME02"
    runner.SUMMARY = ROOT / "data/results/scale_batch_001_mineru_RESUME02_summary.lock.json"
    runner.RESUME_FROM = PARENT
    runner.main()


if __name__ == "__main__":
    main()
