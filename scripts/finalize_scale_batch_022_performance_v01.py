from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERFORMANCE = ROOT / "data/results/scale_batch_022_performance_baseline.lock.json"
PARENT_PERFORMANCE = ROOT / "data/results/scale_batch_021_performance_baseline.lock.json"
ATTEMPTS = (
    ROOT / "data/results/scale_batch_022_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_022_mineru_RESUME01_summary.lock.json",
    ROOT / "data/results/scale_batch_022_mineru_RESUME02_summary.lock.json",
    ROOT / "data/results/scale_batch_022_mineru_RESUME03_summary.lock.json",
)
FINAL = ROOT / "data/results/scale_batch_022_mineru_FINAL_summary.lock.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    performance = load(PERFORMANCE)
    parent = load(PARENT_PERFORMANCE)
    attempts = [load(path) for path in ATTEMPTS]
    final = load(FINAL)
    successful_times = {
        f"{item['document_id']}:p{item['page']:04d}": item["wall_seconds"]
        for item in final["records"]
    }
    successful_seconds = round(sum(successful_times.values()), 6)
    total_attempt_seconds = round(
        sum(
            item.get("wall_seconds", 0)
            for attempt in attempts
            for item in attempt["records"]
        ),
        6,
    )
    throughput = round(final["complete_pages"] * 3600 / successful_seconds, 6)
    parent_throughput = parent["mineru"]["successful_target_pages_per_hour"]
    performance["status"] = "diagnostic_and_mineru_baseline_complete"
    performance["mineru"] = {
        "target_page_wall_seconds": dict(sorted(successful_times.items())),
        "successful_target_pages": final["complete_pages"],
        "successful_processing_wall_seconds": successful_seconds,
        "successful_target_pages_per_hour": throughput,
        "attempt_wall_seconds": [
            round(sum(item.get("wall_seconds", 0) for item in attempt["records"]), 6)
            for attempt in attempts
        ],
        "total_attempt_wall_seconds": total_attempt_seconds,
        "resume_completed_pages": sum(attempt["complete_pages"] for attempt in attempts[1:]),
        "initial_failures": attempts[0]["failed_pages"],
        "final_complete_pages": final["complete_pages"],
        "post_completion_shutdown_recovered_pages": final[
            "post_completion_shutdown_recovered_pages"
        ],
        "status": "complete_after_audited_resume_and_hash_recovery",
    }
    performance["mineru_comparison"] = {
        "batch_021_pages_per_hour": parent_throughput,
        "batch_022_pages_per_hour": throughput,
        "relative_change_percent": round((throughput / parent_throughput - 1) * 100, 3),
        "interpretation_gate": "throughput_only_quality_measured_separately",
    }
    PERFORMANCE.write_text(json.dumps(performance, indent=2, sort_keys=True) + "\n")
    print(json.dumps(performance["mineru"], sort_keys=True))
    print(json.dumps(performance["mineru_comparison"], sort_keys=True))


if __name__ == "__main__":
    main()
