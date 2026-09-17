from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
MINERU_ATTEMPTS = (
    ROOT / "data/results/scale_batch_020_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_020_mineru_RESUME01_summary.lock.json",
)
DUPLICATE_ATTEMPT = ROOT / "data/manifests/scale_batch_020_acquisition_attempt.lock.json"
FINAL = ROOT / "data/results/scale_batch_020_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for attempt_number, path in enumerate(MINERU_ATTEMPTS):
        for item in builder.read_json(path)["records"]:
            if item["status"] != "failed":
                continue
            records.append(
                builder.failure_record(
                    task_id=(
                        f"MINERU-{'INITIAL' if attempt_number == 0 else 'RESUME01'}-"
                        f"{item['document_id']}-P{item['page']:04d}"
                    ),
                    signature="MINERU_POST_PROCESS_SHUTDOWN_MUTEX_ABORT",
                    category="executor_or_configuration",
                    diagnostic=item,
                    source=path,
                )
            )
    records.append(
        builder.failure_record(
            task_id="SOURCE-DEDUP-KB-B020-AHOLD-AR2025",
            signature="SOURCE_REPORT_SERIES_ALREADY_USED",
            category="reference_integrity",
            diagnostic=builder.read_json(DUPLICATE_ATTEMPT),
            source=DUPLICATE_ATTEMPT,
        )
    )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_020_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_020_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_020_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_020_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_020_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-020"
    builder.TASK_PREFIX = "KB-B020"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
