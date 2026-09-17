from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_ATTEMPT = ROOT / "data/manifests/scale_batch_018_acquisition_attempt.lock.json"
FINAL = ROOT / "data/results/scale_batch_018_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for item in builder.read_json(ACQUISITION_ATTEMPT)["documents"]:
        if item["download_status"] != "failed_preserved":
            continue
        records.append(
            builder.failure_record(
                task_id=f"ACQUIRE-SANDBOX-{item['document_id']}",
                signature="SANDBOX_NETWORK_DNS_DENIED",
                category="cloud_transport",
                diagnostic=item,
                source=ACQUISITION_ATTEMPT,
            )
        )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_018_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_018_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_018_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_018_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_018_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-018"
    builder.TASK_PREFIX = "KB-B018"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
