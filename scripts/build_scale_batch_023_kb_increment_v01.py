from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
MINERU_ATTEMPTS = (
    ROOT / "data/results/scale_batch_023_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_023_mineru_RESUME01_summary.lock.json",
    ROOT / "data/results/scale_batch_023_mineru_RESUME02_summary.lock.json",
)
SOURCE_FAILURES = (
    ROOT / "data/manifests/scale_batch_023_acquisition_failures.lock.json",
    ROOT / "data/manifests/scale_batch_023_assurance_preflight_failures.lock.json",
    ROOT / "data/manifests/scale_batch_023_RESUME02_preflight_failure.lock.json",
)
FINAL = ROOT / "data/results/scale_batch_023_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for path in SOURCE_FAILURES:
        payload = builder.read_json(path)
        items = payload.get("failures", [payload])
        for index, item in enumerate(items, start=1):
            signature = item["failure_signature"]
            category = (
                "cloud_transport"
                if signature == "OFFICIAL_SOURCE_HTTP_403"
                else "parser_or_document_structure"
            )
            records.append(
                builder.failure_record(
                    task_id=f"PREFLIGHT-B023-{index}-{signature}",
                    signature=signature,
                    category=category,
                    diagnostic=item,
                    source=path,
                )
            )
    for label, path in zip(
        ("INITIAL", "RESUME01", "RESUME02"), MINERU_ATTEMPTS, strict=True
    ):
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
    builder.TARGETS = (
        ROOT / "data/manifests/scale_batch_023_RESUME02_target_pages.lock.json"
    )
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_023_RESUME02_v0.3.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_023_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_023_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_023_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-023-RESUME02"
    builder.TASK_PREFIX = "KB-B023"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
