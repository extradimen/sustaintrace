from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
MINERU_ATTEMPTS = (
    ROOT / "data/results/scale_batch_024_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_024_mineru_RESUME01_summary.lock.json",
    ROOT / "data/results/scale_batch_024_mineru_RESUME02_summary.lock.json",
    ROOT / "data/results/scale_batch_024_mineru_RESUME03_summary.lock.json",
)
SOURCE_FAILURES = (
    ROOT / "data/manifests/scale_batch_024_assurance_preflight_failures.lock.json",
)
FINAL = ROOT / "data/results/scale_batch_024_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for path in SOURCE_FAILURES:
        payload = builder.read_json(path)
        items = payload.get("failures", [payload])
        for index, item in enumerate(items, start=1):
            signature = item["failure_signature"]
            records.append(
                builder.failure_record(
                    task_id=f"PREFLIGHT-B024-{index}-{signature}",
                    signature=signature,
                    category="parser_or_document_structure",
                    diagnostic=item,
                    source=path,
                )
            )
    for label, path in zip(
        ("INITIAL", "RESUME01", "RESUME02", "RESUME03"),
        MINERU_ATTEMPTS,
        strict=True,
    ):
        for item in builder.read_json(path)["records"]:
            if item["status"] != "failed":
                continue
            signature = (
                "MINERU_SANDBOX_LOOPBACK_BIND_DENIED"
                if label == "INITIAL"
                else "MINERU_POST_PROCESS_SHUTDOWN_MUTEX_ABORT"
            )
            records.append(
                builder.failure_record(
                    task_id=f"MINERU-{label}-{item['document_id']}-P{item['page']:04d}",
                    signature=signature,
                    category="executor_or_configuration",
                    diagnostic=item,
                    source=path,
                )
            )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_024_RESUME01_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_024_RESUME01_v0.2.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_024_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_024_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_024_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-024-RESUME01"
    builder.TASK_PREFIX = "KB-B024"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
