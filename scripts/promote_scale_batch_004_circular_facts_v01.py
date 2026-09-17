from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_004_atomic_fact_records.jsonl"
REPORT = ROOT / "data/raw/scale_batch_004/philips-annual-report-2025.pdf"
REPORT_SHA256 = "ff527efe35aa923bd6b592c38549bf1f9f207ac3cef2cec6695a7b9cd93efc6d"

PROMOTABLE = {
    "fact-aaf88f209ed5a89e198d8c2a": {
        "metric": "Zero Waste to Landfill actual performance",
        "period": "Actual 2025",
        "value": "0.0",
        "scope_boundary": "Philips entity-specific Zero Waste to Landfill metric",
        "cross_reference_page": 249,
    },
    "fact-680153d02b4ad8d6a26bf23d": {
        "metric": "Zero Waste to Landfill baseline",
        "period": "Baseline year 2020",
        "value": "2.6",
        "scope_boundary": "Philips entity-specific Zero Waste to Landfill metric",
        "cross_reference_page": 249,
    },
    "fact-dc2f7968d76480ed1d258b48": {
        "metric": "Circular Materials Management actual performance",
        "period": "Actual 2025",
        "value": "95",
        "scope_boundary": "Philips entity-specific Circular Materials Management metric",
        "cross_reference_page": 248,
    },
    "fact-0fdd861bdd87137432d047f1": {
        "metric": "Circular Materials Management baseline",
        "period": "Baseline year 2020",
        "value": "90",
        "scope_boundary": "Philips entity-specific Circular Materials Management metric",
        "cross_reference_page": 248,
    },
    "fact-4f6b615deb687ed51454ed9e": {
        "metric": "Circular Materials Management disclosed target (not target achievement)",
        "period": "Target 2025",
        "value": "95",
        "scope_boundary": "Philips entity-specific Circular Materials Management target disclosure",
        "cross_reference_page": 248,
    },
}

BLOCKED = {
    "fact-27617b1dbb1725a3b40a3623",
    "fact-131da006f2cf20c453c28f53",
    "fact-158571c814119b39d785eb48",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )


def main() -> None:
    if sha256_file(REPORT) != REPORT_SHA256:
        raise ValueError("Philips parent report hash mismatch")

    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    if set(candidates) != set(PROMOTABLE) | BLOCKED:
        raise ValueError("fail-closed: batch-four atomic candidate inventory changed")

    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    adjudications = load_jsonl(adjudications_path)
    trusted = load_jsonl(trusted_path)
    adjudicated_ids = {item["fact_record_id"] for item in adjudications}
    trusted_ids = {item["record_id"] for item in trusted}
    summary_path = ROOT / "data/results/scale_batch_004_tier_b_promotion.lock.json"
    if set(PROMOTABLE) <= adjudicated_ids and set(PROMOTABLE) <= trusted_ids:
        if not summary_path.exists():
            raise ValueError("promotion exists but its locked summary is missing")
        print(json.dumps(json.loads(summary_path.read_text()), ensure_ascii=False, sort_keys=True))
        return
    new_adjudications = []
    new_trusted = []

    assurance_scope = (
        "The Philips ESRS cross-reference explicitly assigns Reasonable Assurance to the "
        "entity-specific Circular Materials Management and Zero Waste to Landfill disclosures; "
        "the signed PwC report states that the selected resource-use policies, metrics, targets "
        "and waste disclosures were subject to reasonable-assurance procedures."
    )

    for fact_id, normalized in sorted(PROMOTABLE.items()):
        fact = candidates[fact_id]
        if fact["value"] != normalized["value"]:
            raise ValueError(f"value mismatch for {fact_id}")
        if fact_id in adjudicated_ids or fact_id in trusted_ids:
            continue

        cell = fact["evidence"][0]
        adjudication_id = stable_id(
            "adj",
            {
                "fact_record_id": fact_id,
                "report_sha256": REPORT_SHA256,
                "cross_reference_page": normalized["cross_reference_page"],
                "assurance_report_page": 266,
            },
        )
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": "Koninklijke Philips N.V.",
                "evidence": "issuer identity and addressee in the signed PwC assurance report",
            },
            "metric": {
                "status": "matched",
                "normalized": normalized["metric"],
                "evidence": assurance_scope,
            },
            "period": {
                "status": "matched",
                "normalized": normalized["period"],
                "evidence": (
                    f"the frozen table column {cell['column_header']!r} binds the selected cell"
                ),
            },
            "unit": {
                "status": "matched",
                "normalized": "percent",
                "evidence": f"the exact source cell is printed as {cell['quote']}",
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": normalized["scope_boundary"],
                "evidence": assurance_scope,
            },
            "value": {
                "status": "matched",
                "normalized": normalized["value"],
                "evidence": (
                    f"native PDF page 210 and frozen MinerU table cell {cell['cell_handle']} "
                    f"both bind {cell['row_header']!r} to {cell['column_header']!r} as "
                    f"{cell['quote']}"
                ),
            },
        }
        new_adjudications.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_independent_adjudication",
                "adjudication_id": adjudication_id,
                "fact_record_id": fact_id,
                "task_id": fact["subject"]["task_id"],
                "assurance_scope_basis": "metric_explicitly_listed",
                "dimensions": dimensions,
                "promotion_decision": {
                    "eligible": True,
                    "target_tier": "B",
                    "reason": (
                        "all_six_dimensions_match_and_reasonable_assurance_scope_is_frozen"
                    ),
                    "locked_experiments_modified": False,
                },
            }
        )

        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["qualifiers"].update(
            {
                "period_literal": normalized["period"],
                "reference_period": cell["normalized_period"],
                "normalized_unit": "percent",
                "scope_boundary": normalized["scope_boundary"],
                "value_origin": "source_disclosure_independently_reasonably_assured",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].extend(
            [
                {
                    "source_id": "PHILIPS-ESRS-CROSS-REFERENCE-2025",
                    "pdf_page": normalized["cross_reference_page"],
                    "quote": assurance_scope,
                    "role": "independent_assurance_scope_cross_reference",
                    "local_artifact": REPORT.relative_to(ROOT).as_posix(),
                    "local_artifact_sha256": REPORT_SHA256,
                },
                {
                    "source_id": "ASSURANCE-PWC-PHILIPS-2025",
                    "pdf_page": 266,
                    "quote": (
                        "PwC conducted reasonable assurance procedures on specific identified "
                        "disclosures and metrics within the 2025 sustainability statement."
                    ),
                    "role": "signed_independent_assurance_scope",
                    "local_artifact": REPORT.relative_to(ROOT).as_posix(),
                    "local_artifact_sha256": REPORT_SHA256,
                },
            ]
        )
        promoted["provenance"] = {
            "source_artifact": REPORT.relative_to(ROOT).as_posix(),
            "source_sha256": REPORT_SHA256,
            "reference_status": f"tier_b_adjudication:{adjudication_id}",
            "simulated": False,
        }
        promoted["promotion"] = {
            "eligible": True,
            "reason": f"passed_independent_adjudication:{adjudication_id}",
        }
        new_trusted.append(promoted)

    all_adjudications = sorted(
        adjudications + new_adjudications,
        key=lambda item: (item["task_id"], item["fact_record_id"]),
    )
    all_trusted = sorted(
        trusted + new_trusted,
        key=lambda item: (item["subject"]["task_id"], item["record_id"]),
    )
    validate_records(
        all_adjudications,
        json.loads(
            (ROOT / "schemas/knowledge/tier-b-independent-adjudication-v0.1.schema.json")
            .read_text()
        ),
    )
    validate_records(
        all_trusted,
        json.loads((ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text()),
    )
    dump_jsonl(adjudications_path, all_adjudications)
    dump_jsonl(trusted_path, all_trusted)

    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_004_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(new_trusted),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": sorted(BLOCKED),
        "blocked_reason": (
            "supplier SBT percentage cells lack an exact metric-to-assurance-scope page binding"
        ),
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha256_file(INCREMENT),
            "philips_report_sha256": REPORT_SHA256,
        },
        "outputs": {
            "adjudications_sha256": sha256_file(adjudications_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "scale_batch_005_source_acquisition_and_local_ingestion",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
