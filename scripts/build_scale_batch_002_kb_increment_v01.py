from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_FAILURES = (
    ROOT / "data/manifests/scale_batch_002_acquisition_failures.lock.json"
)
INITIAL = ROOT / "data/results/scale_batch_002_mineru_summary.lock.json"
RESUME01 = ROOT / "data/results/scale_batch_002_mineru_RESUME01_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    acquisition = builder.read_json(ACQUISITION_FAILURES)
    for index, attempt in enumerate(acquisition["attempts"], start=1):
        if attempt["result"] != "HTTP_403":
            continue
        records.append(
            builder.failure_record(
                task_id=f"ACQUIRE-{attempt['document_id']}-ATTEMPT-{index}",
                signature="OFFICIAL_SOURCE_HTTP_403",
                category="cloud_transport",
                diagnostic=attempt,
                source=ACQUISITION_FAILURES,
            )
        )
    initial = builder.read_json(INITIAL)
    for item in initial["records"]:
        if item["status"] != "failed":
            continue
        records.append(
            builder.failure_record(
                task_id=f"MINERU-{item['document_id']}-P{item['page']:04d}",
                signature="MINERU_POSTPROCESS_RUNTIME_ABORT",
                category="parser_or_document_structure",
                diagnostic=item,
                source=INITIAL,
            )
        )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_002_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_002_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_002_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_002_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_002_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-002"
    builder.TASK_PREFIX = "KB-B002"
    builder.SUCCESS_SUMMARIES = (INITIAL, RESUME01)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
