from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERFORMANCE = ROOT / "data/results/scale_batch_018_performance_baseline.lock.json"
PARENT_PERFORMANCE = ROOT / "data/results/scale_batch_017_performance_baseline.lock.json"
INITIAL = ROOT / "data/results/scale_batch_018_mineru_summary.lock.json"
FINAL = ROOT / "data/results/scale_batch_018_mineru_FINAL_summary.lock.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    performance = load(PERFORMANCE)
    parent = load(PARENT_PERFORMANCE)
    initial = load(INITIAL)
    final = load(FINAL)
    successful_times = {
        f"{item['document_id']}:p{item['page']:04d}": item["wall_seconds"]
        for item in final["records"]
    }
    successful_seconds = round(sum(successful_times.values()), 6)
    total_attempt_seconds = round(
        sum(item.get("wall_seconds", 0) for item in initial["records"]), 6
    )
    throughput = round(final["complete_pages"] * 3600 / successful_seconds, 6)
    parent_throughput = parent["mineru"]["successful_target_pages_per_hour"]
    performance["status"] = "diagnostic_and_mineru_baseline_complete"
    performance["mineru"] = {
        "target_page_wall_seconds": dict(sorted(successful_times.items())),
        "successful_target_pages": final["complete_pages"],
        "successful_processing_wall_seconds": successful_seconds,
        "successful_target_pages_per_hour": throughput,
        "initial_attempt_wall_seconds": total_attempt_seconds,
        "total_attempt_wall_seconds": total_attempt_seconds,
        "checkpoint_reuse_pages": 0,
        "initial_failures": initial["failed_pages"],
        "post_completion_shutdown_failures": 0,
        "final_complete_pages": final["complete_pages"],
        "status": "complete",
    }
    performance["mineru_comparison"] = {
        "batch_017_pages_per_hour": parent_throughput,
        "batch_018_pages_per_hour": throughput,
        "relative_change_percent": round((throughput / parent_throughput - 1) * 100, 3),
        "interpretation_gate": "throughput_only_quality_measured_separately",
    }
    PERFORMANCE.write_text(json.dumps(performance, indent=2, sort_keys=True) + "\n")
    print(json.dumps(performance["mineru"], sort_keys=True))
    print(json.dumps(performance["mineru_comparison"], sort_keys=True))


if __name__ == "__main__":
    main()
