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
    matrix_path = KB / "tier_b_blocker_matrix.jsonl"
    native_path = KB / "source_native_field_bindings.jsonl"
    matrix = load_jsonl(matrix_path)
    native = {record["fact_record_id"]: record for record in load_jsonl(native_path)}
    records = []
    for item in matrix:
        plan = item["period_plan"]
        if plan not in {
            "exact_year_label_candidate",
            "non_temporal_predicate_gap_misclassification",
        }:
            continue
        binding = native[item["fact_record_id"]]
        if plan == "exact_year_label_candidate":
            predicate_years = sorted(
                set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", item["predicate"]))
            )
            candidate = binding["candidates"][0]
            label_years = sorted(
                set(predicate_years)
                & set(binding.get("required_labels", []))
                & set(candidate.get("found_labels", []))
            )
            if len(label_years) != 1:
                raise ValueError(f"exact year gate failed for {item['fact_record_id']}")
            resolution_type = "exact_source_label"
            resolved_value = label_years[0]
            evidence = (
                f"predicate, required label and source-native page {binding['pdf_page']} "
                f"all bind the exact year {resolved_value}"
            )
        else:
            resolution_type = "not_applicable_non_temporal_field"
            resolved_value = None
            evidence = (
                "controlled predicate classification identifies assurance metadata rather than a "
                "period-indexed measurement"
            )
        effective_blockers = [
            blocker
            for blocker in item["blocking_signatures"]
            if blocker != "PERIOD_ATTACHMENT_INCOMPLETE"
        ]
        identity = {
            "fact_record_id": item["fact_record_id"],
            "resolution_type": resolution_type,
            "resolved_value": resolved_value,
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_blocker_resolution",
                "resolution_id": stable_id("resolution", identity),
                "fact_record_id": item["fact_record_id"],
                "task_id": item["task_id"],
                "resolved_signature": "PERIOD_ATTACHMENT_INCOMPLETE",
                "resolution_type": resolution_type,
                "resolved_value": resolved_value,
                "evidence": evidence,
                "effective_blockers": effective_blockers,
                "effective_status": (
                    "ready_for_independent_source_review"
                    if not effective_blockers
                    else "blocked_additional_qualification"
                ),
                "execution_mode": "derived_layer_only",
                "rollback": "delete_derived_resolution_record",
                "source_fact_modified": False,
                "promotion_performed": False,
            }
        )
    records.sort(key=lambda record: (record["task_id"], record["fact_record_id"]))
    schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-blocker-resolution-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = KB / "tier_b_blocker_resolutions.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    type_counts = Counter(record["resolution_type"] for record in records)
    status_counts = Counter(record["effective_status"] for record in records)
    remaining_period_blockers = sum(
        "PERIOD_ATTACHMENT_INCOMPLETE" in item["blocking_signatures"] for item in matrix
    ) - len(records)
    summary = {
        "schema_version": "0.1",
        "status": "tier_b_period_blockers_resolved_in_derived_layer",
        "resolutions": len(records),
        "resolution_type_counts": dict(sorted(type_counts.items())),
        "effective_status_counts": dict(sorted(status_counts.items())),
        "newly_ready_for_independent_source_review": status_counts[
            "ready_for_independent_source_review"
        ],
        "remaining_period_blockers": remaining_period_blockers,
        "remaining_boundary_blockers": sum(
            "BOUNDARY_ATTACHMENT_INCOMPLETE" in item["blocking_signatures"] for item in matrix
        ),
        "source_fact_records_modified": 0,
        "promotions_performed": 0,
        "rollback_ledgers": len(records),
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "blocker_matrix_sha256": sha256_file(matrix_path),
            "source_native_bindings_sha256": sha256_file(native_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "seek independent sources for newly ready facts and retain boundary semantics under "
            "supervision"
        ),
    }
    summary_path = KB / "tier_b_blocker_resolution_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
