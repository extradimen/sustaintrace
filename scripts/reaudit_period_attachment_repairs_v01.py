from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    repair_path = KB / "period_attachment_repairs.jsonl"
    gap_path = KB / "knowledge_gap_records.jsonl"
    repairs = load(repair_path)
    gap_counts = Counter(item["fact_record_id"] for item in load(gap_path))
    records = []
    for repair in repairs:
        remaining = max(0, gap_counts[repair["fact_record_id"]] - 1)
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "period_repair_reaudit",
                "fact_record_id": repair["fact_record_id"],
                "attachment_id": repair["attachment_id"],
                "period_before": repair["previous_status"],
                "period_after": "exact_frozen_cell_header",
                "remaining_gap_count": remaining,
                "qualification_after": (
                    "jointly_qualified_candidate" if remaining == 0 else "incomplete_qualification"
                ),
                "promotion_performed": False,
            }
        )
    schema = json.loads(
        (ROOT / "schemas/knowledge/period-repair-reaudit-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output = KB / "period_repair_reaudits.jsonl"
    output.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    counts = Counter(item["qualification_after"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "period_repair_reaudit_complete_no_promotion",
        "counts": dict(sorted(counts.items())),
        "promotions_performed": 0,
        "inputs": {
            "period_repairs_sha256": sha256_file(repair_path),
            "knowledge_gaps_sha256": sha256_file(gap_path),
        },
        "output": {
            "path": output.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output),
        },
        "next_gate": "validate deterministic unit attachment without using reference outputs",
    }
    summary_path = KB / "period_repair_reaudit_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
