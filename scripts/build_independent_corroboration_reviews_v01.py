from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


SOURCE_PROFILES: dict[str, dict[str, Any]] = {
    "P17-BMW-GROUP-REPORT-2025": {
        "provider": "PricewaterhouseCoopers GmbH Wirtschaftsprüfungsgesellschaft",
        "title": "Assurance Report of the Independent German Public Auditor",
        "url": "https://www.bmwgroup.com/en/report/2025.html",
        "assurance_standard": "ISAE 3000 (Revised)",
        "assurance_report_pages": [372, 373, 374, 375],
        "parent_artifact": "data/raw/p17_staging/bmw-group-report-2025.pdf",
        "local_artifact": "data/raw/p17_staging/bmw-group-report-2025.pdf",
        "metric_scope_locator": (
            "PwC covers the 2025 Group Sustainability Report with limited assurance; only the "
            "separately marked disclosures receive reasonable assurance"
        ),
        "assurance_scope_status": "statement_level_requires_metric_adjudication",
    },
    "P10-SHELL-AR2025": {
        "provider": "Ernst & Young LLP",
        "title": "Independent Auditor's report related to the Sustainability Statements",
        "url": "https://www.shell.com/investors/results-and-reporting/annual-report.html",
        "assurance_standard": "ISAE 3000 (Revised)",
        "assurance_report_pages": [426, 427],
        "parent_artifact": "data/raw/p10_staging/shell-annual-report-2025.pdf",
        "local_artifact": (
            "data/external/independent_assurance/v0.1/"
            "shell_2025_assurance_extract_pp426-427.pdf"
        ),
        "metric_scope_locator": (
            "EY directly states on source page 427 that its assurance covers pages 335–425"
        ),
        "assurance_scope_status": "direct_independent_statement",
    },
    "P18-DEUTSCHE-TELEKOM-AR2025": {
        "provider": "Deloitte GmbH Wirtschaftsprüfungsgesellschaft",
        "title": (
            "Independent German public auditor's assurance report on the Combined "
            "Sustainability Statement"
        ),
        "url": "https://report.telekom.com/annual-report-2025/",
        "assurance_standard": "ISAE 3000 (Revised)",
        "assurance_report_pages": [370, 371, 372, 373, 374],
        "parent_artifact": (
            "data/raw/p18_staging/deutsche_telekom_annual_report_2025_en.pdf"
        ),
        "local_artifact": (
            "data/external/independent_assurance/v0.1/"
            "deutsche_telekom_2025_assurance_extract_pp370-374.pdf"
        ),
        "metric_scope_locator": (
            "The entire 2025 Combined Sustainability Statement has limited assurance; "
            "the combined Scope 1 and 2 market-based indicator additionally has "
            "reasonable assurance"
        ),
        "assurance_scope_status": "statement_level_requires_metric_adjudication",
    },
    "P19-NOVO-NORDISK-AR2025": {
        "provider": "Deloitte Statsautoriseret Revisionspartnerselskab",
        "title": "Independent auditor's limited assurance report on the Sustainability Statement",
        "url": (
            "https://annualreport.novonordisk.com/2025/_assets/downloads/"
            "novo-nordisk-annual-report-2025.pdf?h=9UdfHgQ-"
        ),
        "assurance_standard": "ISAE 3000 (Revised)",
        "assurance_report_pages": [123, 124],
        "parent_artifact": "data/raw/p19_staging/novo-nordisk-annual-report-2025.pdf",
        "local_artifact": (
            "data/external/independent_assurance/v0.1/"
            "novo_nordisk_2025_assurance_extract_pp123-124.pdf"
        ),
        "metric_scope_locator": (
            "Sustainability Statement for 1 January–31 December 2025; metric-specific "
            "inclusion must be adjudicated after the report is frozen locally"
        ),
        "assurance_scope_status": "statement_level_requires_metric_adjudication",
    },
    "P20-HOLCIM-SS2025": {
        "provider": "EY & Associés",
        "title": (
            "Independent verifier's limited assurance report on selected "
            "nonfinancial information"
        ),
        "url": "https://www.holcim.com/sites/holcim/files/docs/27022026-holcim-sustainability-statement-2025",
        "assurance_standard": "ISAE 3000 (Revised)",
        "assurance_report_pages": [133, 134, 135, 136, 137],
        "parent_artifact": "data/raw/p20_staging/holcim-sustainability-statement-2025.pdf",
        "local_artifact": (
            "data/external/independent_assurance/v0.1/"
            "holcim_2025_assurance_extract_pp133-137.pdf"
        ),
        "metric_scope_locator": (
            "Appendix 1 explicitly lists Absolute Scope 1 emissions – gross and "
            "Absolute Scope 3 emissions – total"
        ),
        "assurance_scope_status": "metric_explicitly_listed",
    },
    "P21-BASF-AR2025": {
        "provider": "Deloitte GmbH Wirtschaftsprüfungsgesellschaft",
        "title": "Limited assurance report in relation to the Combined Sustainability Statement",
        "url": (
            "https://report.basf.com/2025/en/further-information/"
            "assurance-report-in-relation-to-the-combined-sustainability-statement.html"
        ),
        "assurance_standard": "ISAE 3000 (Revised)",
        "assurance_report_pages": [433, 434, 435, 436],
        "parent_artifact": "data/raw/p21_staging/basf-report-2025.pdf",
        "local_artifact": (
            "data/external/independent_assurance/v0.1/"
            "basf_2025_assurance_extract_pp433-436.pdf"
        ),
        "metric_scope_locator": (
            "Combined Sustainability Statement for 1 January–31 December 2025; "
            "E1 climate metrics are not among the stated exclusions, subject to local freeze review"
        ),
        "assurance_scope_status": "statement_level_requires_metric_adjudication",
    },
}

DIRECT_STATEMENT_FACTS = {
    "fact-5aa3ea5a6ab667a59f54393a",
    "fact-94fe27058106272d1ebcacae",
}

EXCLUDED_OR_UNAUDITED_FACTS = {
    "fact-9340e325ddeec5f8b83b6b93",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    queue_path = KB / "tier_b_adjudication_queue.jsonl"
    resolution_path = KB / "tier_b_blocker_resolutions.jsonl"
    coordinate_path = KB / "period_coordinate_adjudications.jsonl"
    boundary_path = KB / "boundary_coordinate_adjudications.jsonl"
    policy_path = ROOT / "configs/knowledge/tier_b_independent_source_policy_v0.1.json"
    queue = {record["fact_record_id"]: record for record in load_jsonl(queue_path)}
    for resolution in load_jsonl(resolution_path):
        if resolution["effective_status"] == "ready_for_independent_source_review":
            queue[resolution["fact_record_id"]] = {
                **queue[resolution["fact_record_id"]],
                "adjudication_status": "ready_for_independent_source_review",
            }
    for adjudication in load_jsonl(coordinate_path):
        if adjudication["effective_status"] == "ready_for_independent_source_review":
            queue[adjudication["fact_record_id"]] = {
                **queue[adjudication["fact_record_id"]],
                "adjudication_status": "ready_for_independent_source_review",
            }
    for adjudication in load_jsonl(boundary_path):
        if adjudication["effective_status"] == "ready_for_independent_source_review":
            queue[adjudication["fact_record_id"]] = {
                **queue[adjudication["fact_record_id"]],
                "adjudication_status": "ready_for_independent_source_review",
            }
    records = []
    for item in queue.values():
        if item["adjudication_status"] != "ready_for_independent_source_review":
            continue
        document_id = item["document_ids"][0]
        profile = SOURCE_PROFILES[document_id]
        if item["fact_record_id"] in EXCLUDED_OR_UNAUDITED_FACTS:
            scope_status = "explicitly_excluded_or_unaudited"
        elif item["fact_record_id"] in DIRECT_STATEMENT_FACTS:
            scope_status = "direct_independent_statement"
        else:
            scope_status = profile["assurance_scope_status"]
        ready_without_scope_review = scope_status in {
            "direct_independent_statement",
            "metric_explicitly_listed",
        }
        local_artifact = ROOT / profile["local_artifact"]
        parent_artifact = ROOT / profile["parent_artifact"]
        if not local_artifact.is_file() or not parent_artifact.is_file():
            raise FileNotFoundError("assurance extract and its frozen parent must exist")
        blockers = ["DIMENSION_ADJUDICATION_PENDING"]
        if scope_status == "explicitly_excluded_or_unaudited":
            blockers = ["INDEPENDENT_ASSURANCE_SCOPE_EXCLUDED_OR_UNAUDITED"]
        elif not ready_without_scope_review:
            blockers.append("METRIC_SCOPE_REQUIRES_ADJUDICATION")
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "independent_corroboration_review",
                "fact_record_id": item["fact_record_id"],
                "task_id": item["task_id"],
                "predicate": item["predicate"],
                "value": item["value"],
                "candidate_source": {
                    "source_class": "independent_assurance_statement",
                    "provider": profile["provider"],
                    "provider_role": "independent_assurance_provider",
                    "title": profile["title"],
                    "url": profile["url"],
                    "assurance_level": "limited_assurance",
                    "assurance_standard": profile["assurance_standard"],
                    "reporting_period": "2025",
                    "local_artifact": profile["local_artifact"],
                    "local_artifact_sha256": sha256_file(local_artifact),
                    "parent_artifact": profile["parent_artifact"],
                    "parent_artifact_sha256": sha256_file(parent_artifact),
                    "evidence_locator": {
                        "assurance_report_pages": profile["assurance_report_pages"],
                        "metric_scope_locator": profile["metric_scope_locator"],
                    },
                },
                "assurance_scope_status": scope_status,
                "review_status": (
                    "frozen_blocked_scope_exclusion"
                    if scope_status == "explicitly_excluded_or_unaudited"
                    else (
                        "frozen_ready_for_dimension_adjudication"
                        if ready_without_scope_review
                        else "frozen_pending_metric_scope_adjudication"
                    )
                ),
                "independent_source_frozen": True,
                "promotion_eligible": False,
                "promotion_blockers": blockers,
                "review_notes": [
                    "The assurance report is independently authored even when issuer-hosted.",
                    "The extracted assurance pages are frozen with their parent artifact hash.",
                    "No locked experiment was modified, rerun, or rescored.",
                ],
            }
        )
    records.sort(key=lambda record: (record["task_id"], record["fact_record_id"]))

    schema_path = ROOT / "schemas/knowledge/independent-corroboration-review-v0.1.schema.json"
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "independent_corroboration_reviews.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    scope_counts = Counter(record["assurance_scope_status"] for record in records)
    status_counts = Counter(record["review_status"] for record in records)
    summary = {
        "schema_version": "0.1",
        "status": "candidate_independent_assurance_sources_discovered_no_promotion",
        "review_records": len(records),
        "unique_candidate_sources": len(
            {record["candidate_source"]["url"] for record in records}
        ),
        "scope_counts": dict(sorted(scope_counts.items())),
        "review_status_counts": dict(sorted(status_counts.items())),
        "independent_sources_locally_frozen": len(
            {record["candidate_source"]["local_artifact"] for record in records}
        ),
        "promoted_to_tier_b": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "tier_b_queue_sha256": sha256_file(queue_path),
            "tier_b_blocker_resolutions_sha256": sha256_file(resolution_path),
            "period_coordinate_adjudications_sha256": sha256_file(coordinate_path),
            "boundary_coordinate_adjudications_sha256": sha256_file(boundary_path),
            "independent_source_policy_sha256": sha256_file(policy_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "adjudicate metric, entity, period, unit, boundary, and value coverage against the "
            "frozen assurance extracts before any Tier B promotion"
        ),
    }
    summary_path = KB / "independent_corroboration_review_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
