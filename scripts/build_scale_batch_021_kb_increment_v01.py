from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
MINERU_ATTEMPTS = (
    ROOT / "data/results/scale_batch_021_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_021_mineru_RESUME01_summary.lock.json",
    ROOT / "data/results/scale_batch_021_mineru_RESUME02_summary.lock.json",
)
ACQUISITION_FAILURES = ROOT / "data/manifests/scale_batch_021_acquisition_failures.lock.json"
FINAL = ROOT / "data/results/scale_batch_021_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for item in builder.read_json(ACQUISITION_FAILURES)["attempts"]:
        company_key = "-".join(item["company"].upper().replace(".", "").split())
        records.append(
            builder.failure_record(
                task_id=f"ACQUIRE-B021-{company_key}",
                signature="OFFICIAL_SOURCE_HTTP_403",
                category="cloud_transport",
                diagnostic=item,
                source=ACQUISITION_FAILURES,
            )
        )
    labels = ("INITIAL", "RESUME01", "RESUME02")
    for label, path in zip(labels, MINERU_ATTEMPTS, strict=True):
        for item in builder.read_json(path)["records"]:
            if item["status"] != "failed":
                continue
            records.append(
                builder.failure_record(
                    task_id=f"MINERU-{label}-{item['document_id']}-P{item['page']:04d}",
                    signature="MINERU_POST_PROCESS_SHUTDOWN_MUTEX_ABORT",
                    category="executor_or_configuration",
                    diagnostic=item,
                    source=path,
                )
            )
    fallback = next(
        item
        for item in builder.read_json(FINAL)["records"]
        if item["document_id"] == "KB-B021-CAPGEMINI-URD2025" and item["page"] == 320
    )
    records.append(
        builder.failure_record(
            task_id="MINERU-TEXT-FALLBACK-KB-B021-CAPGEMINI-URD2025-P0320",
            signature="MINERU_EMPTY_MARKDOWN_CONTENT_LIST_TEXT_AVAILABLE",
            category="parser_or_document_structure",
            diagnostic=fallback,
            source=FINAL,
        )
    )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_021_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_021_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_021_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_021_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_021_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-021"
    builder.TASK_PREFIX = "KB-B021"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
