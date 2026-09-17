from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERFORMANCE = ROOT / "data/results/scale_batch_014_performance_baseline.lock.json"
PARENT_PERFORMANCE = ROOT / "data/results/scale_batch_013_performance_baseline.lock.json"
INITIAL = ROOT / "data/results/scale_batch_014_mineru_summary.lock.json"
RESUME01 = ROOT / "data/results/scale_batch_014_mineru_RESUME01_summary.lock.json"
FINAL = ROOT / "data/results/scale_batch_014_mineru_FINAL_summary.lock.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def elapsed(summary: dict) -> float:
    return round(sum(item.get("wall_seconds", 0) for item in summary["records"]), 6)


def main() -> None:
    performance = load(PERFORMANCE)
    parent = load(PARENT_PERFORMANCE)
    initial = load(INITIAL)
    resume01 = load(RESUME01)
    final = load(FINAL)
    successful_times = {
        f"{item['document_id']}:p{item['page']:04d}": item["wall_seconds"]
        for item in final["records"]
    }
    successful_seconds = round(sum(successful_times.values()), 6)
    throughput = round(final["complete_pages"] * 3600 / successful_seconds, 6)
    parent_throughput = parent["mineru"]["successful_target_pages_per_hour"]
    performance["status"] = "diagnostic_and_mineru_baseline_complete"
    performance["mineru"] = {
        "target_page_wall_seconds": dict(sorted(successful_times.items())),
        "successful_target_pages": final["complete_pages"],
        "successful_processing_wall_seconds": successful_seconds,
        "successful_target_pages_per_hour": throughput,
        "initial_attempt_wall_seconds": elapsed(initial),
        "resume01_wall_seconds": elapsed(resume01),
        "total_attempt_wall_seconds": round(elapsed(initial) + elapsed(resume01), 6),
        "checkpoint_reuse_pages": initial["complete_pages"],
        "initial_failures": initial["failed_pages"],
        "resume01_failures": resume01["failed_pages"],
        "post_completion_shutdown_failures": initial["failed_pages"],
        "final_complete_pages": final["complete_pages"],
        "status": "complete",
    }
    performance["mineru_comparison"] = {
        "batch_013_pages_per_hour": parent_throughput,
        "batch_014_pages_per_hour": throughput,
        "relative_change_percent": round((throughput / parent_throughput - 1) * 100, 3),
        "interpretation_gate": "throughput_only_quality_measured_separately",
    }
    PERFORMANCE.write_text(json.dumps(performance, indent=2, sort_keys=True) + "\n")
    print(json.dumps(performance["mineru"], sort_keys=True))
    print(json.dumps(performance["mineru_comparison"], sort_keys=True))


if __name__ == "__main__":
    main()
