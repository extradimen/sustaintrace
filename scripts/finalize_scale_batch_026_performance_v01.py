from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_026_performance_baseline.lock.json"
PARENT = ROOT / "data/results/scale_batch_025_performance_baseline.lock.json"
DIAGNOSTICS = ROOT / "data/results/scale_batch_026_diagnostics.lock.json"
ATTEMPTS = tuple(
    ROOT / f"data/results/scale_batch_026_mineru{suffix}_summary.lock.json"
    for suffix in ("", "_RESUME01", "_RESUME02", "_RESUME03")
)
FINAL = ROOT / "data/results/scale_batch_026_mineru_FINAL_summary.lock.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite Batch26 performance baseline")
    parent, diagnostics, final = load(PARENT), load(DIAGNOSTICS), load(FINAL)
    attempts = [load(path) for path in ATTEMPTS]
    successful_times = {
        f"{x['document_id']}:p{x['page']:04d}": x["wall_seconds"] for x in final["records"]
    }
    successful_seconds = round(sum(successful_times.values()), 6)
    throughput = round(final["complete_pages"] * 3600 / successful_seconds, 6)
    parent_throughput = parent["mineru"]["successful_target_pages_per_hour"]
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-026-PERFORMANCE",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "mineru_baseline_complete_diagnostic_timing_not_captured",
        "comparison_parent": str(PARENT.relative_to(ROOT)),
        "whole_report_diagnostic": {
            "documents": diagnostics["totals"]["documents"],
            "pdf_pages": diagnostics["totals"]["pdf_pages"],
            "extractable_pages": diagnostics["totals"]["extractable_pages"],
            "wall_seconds": None,
            "pages_per_second": None,
            "status": "not_captured_before_frozen_diagnostic_write_no_duplicate_run",
        },
        "mineru": {
            "target_page_wall_seconds": dict(sorted(successful_times.items())),
            "successful_target_pages": final["complete_pages"],
            "successful_processing_wall_seconds": successful_seconds,
            "successful_target_pages_per_hour": throughput,
            "attempt_wall_seconds": [
                round(sum(x.get("wall_seconds", 0) for x in attempt["records"]), 6)
                for attempt in attempts
            ],
            "total_attempt_wall_seconds": round(
                sum(x.get("wall_seconds", 0) for attempt in attempts for x in attempt["records"]),
                6,
            ),
            "resume_completed_pages": sum(attempt["complete_pages"] for attempt in attempts[1:]),
            "initial_failures": attempts[0]["failed_pages"],
            "initial_failure_class": "sandbox_local_server_port_bind_denied",
            "final_complete_pages": final["complete_pages"],
            "post_completion_shutdown_recovered_pages": final[
                "post_completion_shutdown_recovered_pages"
            ],
            "status": "complete_after_audited_resume_and_hash_recovery",
        },
        "mineru_comparison": {
            "batch_025_pages_per_hour": parent_throughput,
            "batch_026_pages_per_hour": throughput,
            "relative_change_percent": round((throughput / parent_throughput - 1) * 100, 3),
            "interpretation_gate": "throughput_only_quality_measured_separately",
        },
        "policy": {
            "performance_separate_from_knowledge_quality": True,
            "cloud_transmission": False,
            "locked_experiments_modified": False,
            "duplicate_diagnostic_run_avoided": True,
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["mineru_comparison"], sort_keys=True))


if __name__ == "__main__":
    main()
