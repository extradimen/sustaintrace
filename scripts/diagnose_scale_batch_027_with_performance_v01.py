from __future__ import annotations

import json
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/knowledge/scale_batch_027_v0.1.json"
ACQUISITION = ROOT / "data/manifests/scale_batch_027_acquisition.lock.json"
OUTPUT_DIR = ROOT / "data/interim/scale_batch_027"
SUMMARY = ROOT / "data/results/scale_batch_027_diagnostics.lock.json"
PERFORMANCE = ROOT / "data/results/scale_batch_027_performance_baseline.lock.json"
PARENT = ROOT / "data/results/scale_batch_026_performance_baseline.lock.json"


def main() -> None:
    if SUMMARY.exists() or PERFORMANCE.exists():
        raise RuntimeError("refusing to overwrite an existing Batch27 diagnostic result")
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
    parent = json.loads(PARENT.read_text())
    peak_bytes = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    throughput = diagnostics["totals"]["pdf_pages"] / elapsed
    parent_throughput = parent["whole_report_diagnostic"].get("pages_per_second")
    comparison = {
        "batch_026_pages_per_second": parent_throughput,
        "batch_027_pages_per_second": round(throughput, 6),
        "relative_change_percent": (
            round((throughput / parent_throughput - 1) * 100, 3)
            if parent_throughput
            else None
        ),
        "interpretation_gate": "diagnostic_only_not_semantic_quality_or_mineru_speed",
        "status": "parent_unavailable" if parent_throughput is None else "comparable",
    }
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-027-PERFORMANCE",
        "status": "diagnostic_baseline_recorded_target_pages_pending",
        "started_at": started,
        "completed_at": datetime.now(UTC).isoformat(),
        "comparison_parent": str(PARENT.relative_to(ROOT)),
        "whole_report_diagnostic": {
            "documents": diagnostics["totals"]["documents"],
            "pdf_pages": diagnostics["totals"]["pdf_pages"],
            "extractable_pages": diagnostics["totals"]["extractable_pages"],
            "wall_seconds": round(elapsed, 6),
            "pages_per_second": round(throughput, 6),
            "peak_rss_bytes": peak_bytes,
            "peak_rss_mb": round(peak_bytes / 1024 / 1024, 3),
        },
        "provisional_comparison": comparison,
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
            "parent_results_overwritten": False,
        },
    }
    PERFORMANCE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
