from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_ATTEMPTS = (
    ROOT / "data/manifests/scale_batch_017_acquisition_attempt.lock.json",
)
MINERU_ATTEMPTS = (
    ROOT / "data/results/scale_batch_017_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_017_mineru_RESUME01_summary.lock.json",
)
FINAL = ROOT / "data/results/scale_batch_017_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for item in builder.read_json(ACQUISITION_ATTEMPTS[0])["documents"]:
        if item["download_status"] != "failed_preserved":
            continue
        records.append(
            builder.failure_record(
                task_id=f"ACQUIRE-SANDBOX-{item['document_id']}",
                signature="SANDBOX_NETWORK_DNS_DENIED",
                category="cloud_transport",
                diagnostic=item,
                source=ACQUISITION_ATTEMPTS[0],
            )
        )
    for attempt_number, path in enumerate(MINERU_ATTEMPTS):
        label = "INITIAL" if attempt_number == 0 else "RESUME01"
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
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_017_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_017_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_017_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_017_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_017_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-017"
    builder.TASK_PREFIX = "KB-B017"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
