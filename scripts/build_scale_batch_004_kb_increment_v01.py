from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
INITIAL_ACQUISITION = ROOT / "data/manifests/scale_batch_004_acquisition.lock.json"
RESUME_ACQUISITION = ROOT / "data/manifests/scale_batch_004_acquisition_RESUME01.lock.json"
INITIAL_MINERU = ROOT / "data/results/scale_batch_004_mineru_summary.lock.json"
RESUME_MINERU = ROOT / "data/results/scale_batch_004_mineru_RESUME01_summary.lock.json"
RESUME02_MINERU = ROOT / "data/results/scale_batch_004_mineru_RESUME02_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for item in builder.read_json(INITIAL_ACQUISITION)["documents"]:
        if item["download_status"] != "failed_preserved":
            continue
        records.append(
            builder.failure_record(
                task_id=f"ACQUIRE-{item['document_id']}-SANDBOX",
                signature="SANDBOX_NETWORK_DNS_DENIED",
                category="executor_or_configuration",
                diagnostic=item,
                source=INITIAL_ACQUISITION,
            )
        )
    for item in builder.read_json(RESUME_ACQUISITION)["documents"]:
        if item["download_status"] != "failed_preserved":
            continue
        records.append(
            builder.failure_record(
                task_id=f"ACQUIRE-{item['document_id']}-OFFICIAL",
                signature="OFFICIAL_SOURCE_HTTP_403",
                category="cloud_transport",
                diagnostic=item,
                source=RESUME_ACQUISITION,
            )
        )
    for item in builder.read_json(INITIAL_MINERU)["records"]:
        if item["status"] != "failed":
            continue
        records.append(
            builder.failure_record(
                task_id=f"MINERU-{item['document_id']}-P{item['page']:04d}",
                signature="SANDBOX_LOOPBACK_PORT_DENIED",
                category="executor_or_configuration",
                diagnostic=item,
                source=INITIAL_MINERU,
            )
        )
    for item in builder.read_json(RESUME_MINERU)["records"]:
        if item["status"] != "failed":
            continue
        records.append(
            builder.failure_record(
                task_id=f"MINERU-RESUME01-{item['document_id']}-P{item['page']:04d}",
                signature="MINERU_POSTPROCESS_RUNTIME_ABORT",
                category="parser_or_document_structure",
                diagnostic=item,
                source=RESUME_MINERU,
            )
        )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_004_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_004_RESUME01_v0.2.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_004_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_004_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_004_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-004-RESUME01"
    builder.TASK_PREFIX = "KB-B004"
    builder.SUCCESS_SUMMARIES = (RESUME_MINERU, RESUME02_MINERU)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
