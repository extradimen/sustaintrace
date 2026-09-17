from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS = (
    ROOT / "data/results/scale_batch_029_mineru_summary.lock.json",
    ROOT / "data/results/scale_batch_029_mineru_RESUME01_summary.lock.json",
    ROOT / "data/results/scale_batch_029_mineru_RESUME02_summary.lock.json",
    ROOT / "data/results/scale_batch_029_mineru_RESUME03_summary.lock.json",
)
FINAL = ROOT / "data/results/scale_batch_029_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    labels = ("INITIAL", "RESUME01", "RESUME02", "RESUME03")
    for label, path in zip(labels, ATTEMPTS, strict=True):
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
    builder.TARGETS = ROOT / "data/manifests/scale_batch_029_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_029_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_029_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_029_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_029_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-029"
    builder.TASK_PREFIX = "KB-B028"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
