from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    fact_path = KB / "fact_records.jsonl"
    joint_path = KB / "joint_fact_qualifications.jsonl"
    gap_path = KB / "knowledge_gap_records.jsonl"
    parent_hashes = {
        path.relative_to(ROOT).as_posix(): sha256_file(path)
        for path in (fact_path, joint_path, gap_path)
    }
    qualifications = {item["fact_record_id"]: item for item in load_jsonl(joint_path)}
    all_gaps = load_jsonl(gap_path)
    gap_counts = Counter(item["fact_record_id"] for item in all_gaps)
    records = []
    for gap in all_gaps:
        if gap["gap_signature"] != "PERIOD_ATTACHMENT_INCOMPLETE":
            continue
        qualification = qualifications[gap["fact_record_id"]]
        matches = qualification["table_cell_binding"].get("matches", [])
        if len(matches) != 1:
            continue
        years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", str(matches[0]["column"]))
        if len(set(years)) != 1:
            continue
        identity = {"fact_record_id": gap["fact_record_id"], "period": years[0]}
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "period_attachment_repair",
                "attachment_id": stable_id("period", identity),
                "fact_record_id": gap["fact_record_id"],
                "task_id": gap["task_id"],
                "previous_status": qualification["period_binding"]["status"],
                "attached_period": years[0],
                "evidence_coordinate": matches[0],
                "execution_mode": "derived_layer_only",
                "parent_artifacts": [
                    {"path": path, "sha256": digest}
                    for path, digest in sorted(parent_hashes.items())
                ],
                "validation": {
                    "unique_cell": True,
                    "year_literal_in_column": True,
                    "parent_hashes_valid": True,
                },
                "rollback": {
                    "action": "delete_derived_attachment_record",
                    "source_restoration_required": False,
                },
                "fact_source_modified": False,
                "promotion_performed": False,
            }
        )

    schema = json.loads(
        (ROOT / "schemas/knowledge/period-attachment-repair-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = KB / "period_attachment_repairs.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    immediate_lift = sum(gap_counts[item["fact_record_id"]] == 1 for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "derived_period_repairs_executed_no_fact_promotion",
        "attachments_created": len(records),
        "facts_with_only_period_gap_before_repair": immediate_lift,
        "fact_sources_modified": 0,
        "promotions_performed": 0,
        "rollback_ledgers": len(records),
        "parent_artifacts": [
            {"path": path, "sha256": digest} for path, digest in sorted(parent_hashes.items())
        ],
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "re-audit repaired facts and then validate unit attachment candidates",
    }
    summary_path = KB / "period_attachment_repair_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"attachments": len(records), "immediate_lift": immediate_lift}))


if __name__ == "__main__":
    main()
