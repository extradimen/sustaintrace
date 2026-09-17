from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

NON_TEMPORAL_PREDICATES = {
    "assurance_provider",
    "conclusion_form",
    "governing_standard",
    "incorporated_reference_pages",
    "location",
    "page_range_coverage_page_427",
    "signatory",
    "signature_location",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def predicate_years(predicate: str) -> list[str]:
    return sorted(set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", predicate)))


def period_plan(
    predicate: str,
    blockers: list[str],
    required_labels: list[str],
    found_labels: list[str],
) -> tuple[str, str]:
    if "PERIOD_ATTACHMENT_INCOMPLETE" not in blockers:
        return "not_blocked", "period qualification is not blocking this fact"
    if predicate in NON_TEMPORAL_PREDICATES:
        return (
            "non_temporal_predicate_gap_misclassification",
            "the field describes assurance metadata rather than a period-indexed measurement",
        )
    years = predicate_years(predicate)
    label_years = sorted(set(required_labels) & set(found_labels) & set(years))
    if len(years) == 1 and label_years == years:
        return (
            "exact_year_label_candidate",
            "one predicate year is also an exact required and found source-native label",
        )
    if len(years) == 1:
        return (
            "explicit_predicate_year_requires_coordinate",
            "the predicate has one year but a frozen row-column coordinate must still bind it",
        )
    return (
        "ambiguous_or_role_specific",
        "no single report, baseline, target or signature year is safely selected",
    )


def boundary_plan(predicate: str, blockers: list[str]) -> tuple[str, str]:
    if "BOUNDARY_ATTACHMENT_INCOMPLETE" not in blockers:
        return "not_blocked", "boundary qualification is not blocking this fact"
    explicit_tokens = (
        "germany",
        "international",
        "market",
        "gross",
        "permanent",
        "renewable",
        "temporary",
        "total",
    )
    if any(token in predicate.casefold() for token in explicit_tokens):
        return (
            "explicit_label_candidate",
            "predicate contains a boundary label, but source-local attachment is still required",
        )
    return (
        "semantic_supervision_required",
        "the boundary cannot be selected from a controlled predicate label alone",
    )


def main() -> None:
    queue_path = KB / "tier_b_adjudication_queue.jsonl"
    native_path = KB / "source_native_field_bindings.jsonl"
    queue = [
        record
        for record in load_jsonl(queue_path)
        if record["adjudication_status"] == "blocked_additional_qualification"
    ]
    native = {record["fact_record_id"]: record for record in load_jsonl(native_path)}
    records = []
    for item in queue:
        binding = native[item["fact_record_id"]]
        candidate = binding.get("candidates", [{}])[0]
        context = candidate.get("context", "")
        context_years = sorted(
            set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", context))
        )
        period, period_reason = period_plan(
            item["predicate"],
            item["qualification_blockers"],
            binding.get("required_labels", []),
            candidate.get("found_labels", []),
        )
        boundary, boundary_reason = boundary_plan(
            item["predicate"], item["qualification_blockers"]
        )
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_blocker_matrix_item",
                "fact_record_id": item["fact_record_id"],
                "task_id": item["task_id"],
                "predicate": item["predicate"],
                "blocking_signatures": item["qualification_blockers"],
                "source_native_page": binding.get("pdf_page"),
                "context_years": context_years,
                "period_plan": period,
                "boundary_plan": boundary,
                "execution_allowed": False,
                "reason": f"period: {period_reason}; boundary: {boundary_reason}",
            }
        )
    records.sort(key=lambda record: (record["task_id"], record["fact_record_id"]))
    schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-blocker-matrix-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = KB / "tier_b_blocker_matrix.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    period_counts = Counter(record["period_plan"] for record in records)
    boundary_counts = Counter(record["boundary_plan"] for record in records)
    summary = {
        "schema_version": "0.1",
        "status": "tier_b_blocker_matrix_complete_no_repairs_executed",
        "records": len(records),
        "period_plan_counts": dict(sorted(period_counts.items())),
        "boundary_plan_counts": dict(sorted(boundary_counts.items())),
        "exact_year_label_candidates": period_counts["exact_year_label_candidate"],
        "non_temporal_period_gap_misclassifications": period_counts[
            "non_temporal_predicate_gap_misclassification"
        ],
        "repairs_executed": 0,
        "promotions_performed": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "tier_b_queue_sha256": sha256_file(queue_path),
            "source_native_bindings_sha256": sha256_file(native_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "validate exact-year label candidates and correct non-temporal period classification "
            "in a derived layer"
        ),
    }
    summary_path = KB / "tier_b_blocker_matrix_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
