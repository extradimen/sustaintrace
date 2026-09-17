from __future__ import annotations

from pathlib import Path

import build_scale_batch_kb_increment_v01 as builder

ROOT = Path(__file__).resolve().parents[1]
INITIAL = ROOT / "data/results/scale_batch_006_mineru_summary.lock.json"
RESUMES = tuple(
    ROOT / f"data/results/scale_batch_006_mineru_RESUME0{index}_summary.lock.json"
    for index in (1, 2, 3)
)
FINAL = ROOT / "data/results/scale_batch_006_mineru_FINAL_summary.lock.json"


def build_failure_records() -> list[dict]:
    records = []
    for item in builder.read_json(INITIAL)["records"]:
        if item["status"] != "failed":
            continue
        records.append(
            builder.failure_record(
                task_id=f"MINERU-{item['document_id']}-P{item['page']:04d}",
                signature="SANDBOX_LOOPBACK_PORT_DENIED",
                category="executor_or_configuration",
                diagnostic=item,
                source=INITIAL,
            )
        )
    for attempt_number, path in enumerate(RESUMES, start=1):
        for item in builder.read_json(path)["records"]:
            if item["status"] != "failed":
                continue
            records.append(
                builder.failure_record(
                    task_id=(
                        f"MINERU-RESUME0{attempt_number}-{item['document_id']}-"
                        f"P{item['page']:04d}"
                    ),
                    signature="MINERU_POST_PROCESS_SHUTDOWN_MUTEX_ABORT",
                    category="executor_or_configuration",
                    diagnostic=item,
                    source=path,
                )
            )
    return records


def main() -> None:
    builder.TARGETS = ROOT / "data/manifests/scale_batch_006_target_pages.lock.json"
    builder.SOURCE_CONFIG = ROOT / "configs/knowledge/scale_batch_006_v0.1.json"
    builder.FACT_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_006_fact_records.jsonl"
    )
    builder.FAILURE_OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_006_failure_records.jsonl"
    )
    builder.SUMMARY = ROOT / "data/results/scale_batch_006_kb_increment.lock.json"
    builder.BATCH_ID = "KB-SCALE-BATCH-006"
    builder.TASK_PREFIX = "KB-B006"
    builder.SUCCESS_SUMMARIES = (FINAL,)
    builder.build_failure_records = build_failure_records
    builder.main()


if __name__ == "__main__":
    main()
