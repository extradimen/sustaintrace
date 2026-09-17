from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

# Frozen, manually audited coordinates. These are qualifications in a derived layer, not repairs
# to source facts and not promotions. Each coordinate was checked against the native PDF layout.
SPECS: dict[str, dict[str, Any]] = {
    "fact-041d636e29fb4342bca2b91f": {
        "period": "2024",
        "role": "reporting_year",
        "method": "narrative_relation",
        "text": (
            "the opex denominator will retrospectively increase from the EUR 0.4 billion "
            "previously reported to EUR 2.9 billion for the 2024 financial year"
        ),
        "coordinate": (
            "One sentence binds both the previously reported EUR 0.4 billion and the revised "
            "EUR 2.9 billion denominator to financial year 2024."
        ),
    },
    "fact-212785ada7dac75b836ae699": {
        "period": "2024",
        "role": "reporting_year",
        "method": "table_header_column_position",
        "text": "Gross Scope 1 emissions | 15.369 | 15.115 | 15.556c | 15.220c",
        "coordinate": (
            "In the page-194 table, 15.556c is the Gross Scope 1 cell under the 2024 / "
            "Financial control column; footnote c marks the comparative figure as adjusted."
        ),
    },
    "fact-ef71816124680daff75eb6df": {
        "period": "2024",
        "role": "reporting_year",
        "method": "table_header_column_position",
        "text": "Gross market-based Scope 2 emissions | 1.901 | 2.052 | 2.396 | 2.460",
        "coordinate": (
            "In the page-194 table, 2.396 is the Gross market-based Scope 2 cell under the "
            "2024 / Financial control column."
        ),
    },
    "fact-40aca017502b9df9b11982d8": {
        "period": "2024",
        "role": "reporting_year",
        "method": "table_header_column_position",
        "text": "1 – Purchased goods and services | 52.56 | 54.39 | 51.54c | 53.33c",
        "coordinate": (
            "The repeated page-195 table header maps the third numeric cell, 51.54c, to "
            "2024 / Financial control; footnote c marks it as adjusted."
        ),
    },
    "fact-8f1c36a0aacaf76887386a80": {
        "period": "2024",
        "role": "reporting_year",
        "method": "table_header_column_position",
        "text": "12 – End-of-life treatment of sold products | 27.17 | 27.79 | 25.67c | 26.19c",
        "coordinate": (
            "The repeated page-195 table header maps the third numeric cell, 25.67c, to "
            "2024 / Financial control; footnote c marks it as adjusted."
        ),
    },
    "fact-8fe1c8be8ea7aa849072ba0f": {
        "period": "2024",
        "role": "reporting_year",
        "method": "table_header_column_position",
        "text": "Total gross Scope 3 emissions | 93.97 | 96.52 | 92.33c | 94.59c",
        "coordinate": (
            "The repeated page-195 table header maps the third numeric cell, 92.33c, to "
            "2024 / Financial control; footnote c marks it as adjusted."
        ),
    },
    "fact-c55b9e3044693eae5b62d18e": {
        "period": "2045",
        "role": "target_year",
        "method": "target_clause",
        "text": (
            "Net zero greenhouse gas emissions across our full value chain by 2045: "
            "90% absolute reduction in emissions from a 2020 baseline"
        ),
        "coordinate": (
            "The same target clause binds 90% to target year 2045 and baseline year 2020."
        ),
    },
    "fact-f216f8cbb3e2c3cc919d7b20": {
        "period": "2030",
        "role": "target_year",
        "method": "target_clause",
        "text": (
            "80% absolute reduction in greenhouse gas emissions from a 2020 baseline, "
            "across all scopes"
        ),
        "coordinate": (
            "The target bullet continues through 'footprint by 2030', binding 80% to target "
            "year 2030 and baseline year 2020."
        ),
    },
    "fact-613133ef28d2d55bb47991eb": {
        "period": "2020",
        "role": "baseline_year",
        "method": "baseline_clause",
        "text": "decrease of 30% for overall water use from our 2020 baseline",
        "coordinate": "The same clause explicitly binds the 30% decrease to the 2020 baseline.",
    },
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    matrix_path = KB / "tier_b_blocker_matrix.jsonl"
    facts_path = KB / "fact_records.jsonl"
    prior_resolution_path = KB / "tier_b_blocker_resolutions.jsonl"
    matrix = {record["fact_record_id"]: record for record in load_jsonl(matrix_path)}
    facts = {record["record_id"]: record for record in load_jsonl(facts_path)}
    prior_ids = {
        record["fact_record_id"] for record in load_jsonl(prior_resolution_path)
    }
    records = []
    for fact_id, spec in SPECS.items():
        item = matrix[fact_id]
        fact = facts[fact_id]
        if fact_id in prior_ids:
            raise ValueError(f"period already resolved: {fact_id}")
        if item["period_plan"] != "explicit_predicate_year_requires_coordinate":
            raise ValueError(f"unexpected period plan: {fact_id}")
        if "PERIOD_ATTACHMENT_INCOMPLETE" not in item["blocking_signatures"]:
            raise ValueError(f"missing period blocker: {fact_id}")
        document = fact["subject"]["document_metadata"][0]
        artifact = ROOT / document["local_path"]
        if sha256_file(artifact) != document["sha256"]:
            raise ValueError(f"source artifact hash mismatch: {fact_id}")
        effective_blockers = [
            blocker
            for blocker in item["blocking_signatures"]
            if blocker != "PERIOD_ATTACHMENT_INCOMPLETE"
        ]
        identity = {
            "fact_record_id": fact_id,
            "selected_period": spec["period"],
            "period_role": spec["role"],
            "coordinate_method": spec["method"],
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "period_coordinate_adjudication",
                "adjudication_id": stable_id("period-adj", identity),
                "fact_record_id": fact_id,
                "task_id": item["task_id"],
                "predicate": item["predicate"],
                "value": fact["value"],
                "selected_period": spec["period"],
                "period_role": spec["role"],
                "coordinate_method": spec["method"],
                "source_artifact": document["local_path"],
                "source_artifact_sha256": document["sha256"],
                "source_page": item["source_native_page"],
                "source_text": spec["text"],
                "coordinate_description": spec["coordinate"],
                "resolved_signature": "PERIOD_ATTACHMENT_INCOMPLETE",
                "effective_blockers": effective_blockers,
                "effective_status": (
                    "ready_for_independent_source_review"
                    if not effective_blockers
                    else "blocked_additional_qualification"
                ),
                "execution_mode": "derived_layer_only",
                "rollback": "delete_period_coordinate_adjudication",
                "source_fact_modified": False,
                "promotion_performed": False,
            }
        )
    records.sort(key=lambda record: (record["task_id"], record["fact_record_id"]))
    schema = json.loads(
        (ROOT / "schemas/knowledge/period-coordinate-adjudication-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = KB / "period_coordinate_adjudications.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    statuses = Counter(record["effective_status"] for record in records)
    unresolved = [
        item
        for fact_id, item in matrix.items()
        if "PERIOD_ATTACHMENT_INCOMPLETE" in item["blocking_signatures"]
        and fact_id not in prior_ids
        and fact_id not in SPECS
    ]
    summary = {
        "schema_version": "0.1",
        "status": "explicit_period_coordinates_adjudicated_in_derived_layer",
        "adjudications": len(records),
        "period_role_counts": dict(sorted(Counter(r["period_role"] for r in records).items())),
        "coordinate_method_counts": dict(
            sorted(Counter(r["coordinate_method"] for r in records).items())
        ),
        "newly_ready_for_independent_source_review": statuses[
            "ready_for_independent_source_review"
        ],
        "still_boundary_blocked_after_period_resolution": statuses[
            "blocked_additional_qualification"
        ],
        "remaining_period_blockers": len(unresolved),
        "remaining_period_blocker_fact_ids": sorted(item["fact_record_id"] for item in unresolved),
        "remaining_boundary_blockers": sum(
            "BOUNDARY_ATTACHMENT_INCOMPLETE" in item["blocking_signatures"]
            for item in matrix.values()
        ),
        "source_fact_records_modified": 0,
        "promotions_performed": 0,
        "rollback_ledgers": len(records),
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "blocker_matrix_sha256": sha256_file(matrix_path),
            "fact_records_sha256": sha256_file(facts_path),
            "prior_period_resolutions_sha256": sha256_file(prior_resolution_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "independently corroborate the three newly ready BASF facts; retain four truly "
            "ambiguous period blockers; address boundary semantics separately"
        ),
    }
    summary_path = KB / "period_coordinate_adjudication_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
