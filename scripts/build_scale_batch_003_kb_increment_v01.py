from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_ATTEMPTS = (
    ROOT / "data/manifests/scale_batch_003_acquisition.lock.json",
    ROOT / "data/manifests/scale_batch_003_acquisition_RESUME01.lock.json",
)
INITIAL = ROOT / "data/results/scale_batch_003_mineru_summary.lock.json"
RESUME01 = ROOT / "data/results/scale_batch_003_mineru_RESUME01_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for attempt_number, path in enumerate(ACQUISITION_ATTEMPTS, 1):
        for item in builder.read_json(path)["documents"]:
            if item["download_status"] != "failed_preserved":
                continue
            signature = (
                "OFFICIAL_SOURCE_HTTP_403"
                if "403" in item.get("error", "")
                else "OFFICIAL_SOURCE_READ_TIMEOUT"
            )
            records.append(
                builder.failure_record(
                    task_id=(
                        f"ACQUIRE-{item['document_id']}-ATTEMPT-{attempt_number}"
                    ),
                    signature=signature,
                    category="cloud_transport",
                    diagnostic=item,
                    source=path,
                )
            )
    for item in builder.read_json(INITIAL)["records"]:
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
    builder.TARGETS = ROOT / "data/manifests/scale_batch_003_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_003_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_003_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_003_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_003_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-003"
    builder.TASK_PREFIX = "KB-B003"
    builder.SUCCESS_SUMMARIES = (INITIAL, RESUME01)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
