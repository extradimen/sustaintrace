from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_ATTEMPTS = (
    ROOT / "data/manifests/scale_batch_012_acquisition_attempt.lock.json",
    ROOT / "data/manifests/scale_batch_012_acquisition.lock.json",
)
MINERU_ATTEMPTS = (
    ROOT / "data/results/scale_batch_012_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_012_mineru_RESUME01_summary.lock.json",
)
FINAL = ROOT / "data/results/scale_batch_012_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for attempt_number, path in enumerate(ACQUISITION_ATTEMPTS):
        label = "SANDBOX" if attempt_number == 0 else "INITIAL"
        for item in builder.read_json(path)["documents"]:
            if item["download_status"] != "failed_preserved":
                continue
            signature = (
                "SANDBOX_NETWORK_DNS_DENIED"
                if attempt_number == 0
                else "OFFICIAL_SOURCE_HTTP_403"
            )
            records.append(
                builder.failure_record(
                    task_id=f"ACQUIRE-{label}-{item['document_id']}",
                    signature=signature,
                    category="cloud_transport",
                    diagnostic=item,
                    source=path,
                )
            )
    signatures = (
        "MINERU_POST_PROCESS_SHUTDOWN_MUTEX_ABORT",
        "SANDBOX_LOCALHOST_BIND_DENIED",
    )
    for attempt_number, path in enumerate(MINERU_ATTEMPTS):
        label = "INITIAL" if attempt_number == 0 else "RESUME01"
        for item in builder.read_json(path)["records"]:
            if item["status"] != "failed":
                continue
            records.append(
                builder.failure_record(
                    task_id=f"MINERU-{label}-{item['document_id']}-P{item['page']:04d}",
                    signature=signatures[attempt_number],
                    category="executor_or_configuration",
                    diagnostic=item,
                    source=path,
                )
            )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_012_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_012_RESUME01_v0.2.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_012_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_012_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_012_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-012"
    builder.TASK_PREFIX = "KB-B012"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
