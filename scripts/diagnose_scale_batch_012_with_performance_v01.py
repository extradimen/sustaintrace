from __future__ import annotations

import json
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/knowledge/scale_batch_012_RESUME01_v0.2.json"
ACQUISITION = ROOT / "data/manifests/scale_batch_012_acquisition_FINAL.lock.json"
OUTPUT_DIR = ROOT / "data/interim/scale_batch_012"
SUMMARY = ROOT / "data/results/scale_batch_012_diagnostics.lock.json"
PERFORMANCE = ROOT / "data/results/scale_batch_012_performance_baseline.lock.json"
PARENT_PERFORMANCE = ROOT / "data/results/scale_batch_011_performance_baseline.lock.json"


def main() -> None:
    if SUMMARY.exists() or PERFORMANCE.exists():
        raise RuntimeError("refusing to overwrite an existing diagnostic or performance result")
    command = [
        sys.executable,
        str(ROOT / "scripts/diagnose_scale_batch_v01.py"),
        "--config",
        str(CONFIG),
        "--acquisition",
        str(ACQUISITION),
        "--output-dir",
        str(OUTPUT_DIR),
        "--summary",
        str(SUMMARY),
    ]
    started = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    diagnostics = json.loads(SUMMARY.read_text())
    parent = json.loads(PARENT_PERFORMANCE.read_text())
    peak_bytes = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    current_throughput = diagnostics["totals"]["pdf_pages"] / elapsed
    parent_throughput = parent["whole_report_diagnostic"]["pages_per_second"]
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-012-PERFORMANCE",
        "status": "diagnostic_baseline_recorded_target_pages_pending",
        "started_at": started,
        "completed_at": datetime.now(UTC).isoformat(),
        "comparison_parent": "data/results/scale_batch_011_performance_baseline.lock.json",
        "whole_report_diagnostic": {
            "documents": diagnostics["totals"]["documents"],
            "pdf_pages": diagnostics["totals"]["pdf_pages"],
            "extractable_pages": diagnostics["totals"]["extractable_pages"],
            "wall_seconds": round(elapsed, 6),
            "pages_per_second": round(current_throughput, 6),
            "peak_rss_bytes": peak_bytes,
            "peak_rss_mb": round(peak_bytes / 1024 / 1024, 3),
        },
        "provisional_comparison": {
            "batch_011_pages_per_second": parent_throughput,
            "batch_012_pages_per_second": round(current_throughput, 6),
            "relative_change_percent": round((current_throughput / parent_throughput - 1) * 100, 3),
            "interpretation_gate": "diagnostic_only_not_semantic_quality_or_mineru_speed",
        },
        "mineru": {
            "target_page_wall_seconds": {},
            "successful_target_pages_per_hour": None,
            "initial_failure_wall_seconds": 0,
            "resume_wall_seconds": 0,
            "checkpoint_reuse_pages": 0,
            "status": "pending_target_page_execution",
        },
        "policy": {
            "performance_separate_from_knowledge_quality": True,
            "cloud_transmission": False,
            "locked_experiments_modified": False,
        },
    }
    PERFORMANCE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
