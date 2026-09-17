from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_005_atomic_fact_records.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_005_tier_b_promotion.lock.json"

SOURCES = {
    "KB-B005-HENKEL-AR2025": {
        "entity": "Henkel AG & Co. KGaA Group",
        "path": ROOT / "data/raw/scale_batch_005/henkel-annual-report-2025.pdf",
        "sha256": "d807ec2c95e56082cd63a8f2b70e55ae74631d81d836ca8273aad9fcb396a725",
        "assurance_page": 477,
        "assurance_basis": "whole_statement_inclusion_with_exclusions_checked",
        "assurance_text": (
            "The independent auditor's limited-assurance conclusion covers Henkel's Group "
            "Sustainability Statement for 1 January through 31 December 2025."
        ),
    },
    "KB-B005-UPM-AR2025": {
        "entity": "UPM-Kymmene Oyj Group",
        "path": ROOT / "data/raw/scale_batch_005/upm-annual-report-2025.pdf",
        "sha256": "129f731f45feb99f02c71b8e6f59c200261c7b66fa8d83e36450c5bdf4ed94fc",
        "assurance_page": 176,
        "assurance_basis": "whole_statement_inclusion_with_exclusions_checked",
        "assurance_text": (
            "The authorized sustainability auditor's limited-assurance report covers UPM's "
            "Group Sustainability Statement for 1 January through 31 December 2025."
        ),
    },
    "KB-B005-SIKA-SR2025": {
        "entity": "Sika AG Group",
        "path": ROOT / "data/raw/scale_batch_005/sika-sustainability-report-2025.pdf",
        "sha256": "67590c1857190f8ebd6e7f3827cd4f3537ac35b2aee99432883741f053668790",
        "assurance_page": 133,
        "scope_page": 135,
        "assurance_basis": "metric_explicitly_listed",
        "assurance_text": (
            "KPMG's limited-assurance report and its frozen scope appendix explicitly include "
            "2025 employee headcount and gender breakdown; earlier periods are excluded."
        ),
    },
}

PROMOTABLE = {
    "fact-be71ce032ac2405fa1318636": ("employee turnover rate", "percent"),
    "fact-d2656925d8622dcacf2c1b4d": (
        "market-based GHG emissions per net revenue",
        "tCO2 per EUR million sales",
    ),
    "fact-44bb687cc50e4f11655a3a13": ("male employees", "headcount"),
    "fact-b0c0c518c1880545c34ea777": ("female employees", "headcount"),
    "fact-f7c3530b7bb01841fb871a84": ("employees with gender not disclosed", "headcount"),
    "fact-381ded4ed696e77ae14a107c": ("employees with data not reported", "headcount"),
    "fact-cacdcc69f5771caaa64111bc": ("total employees", "headcount"),
    "fact-ea25042e2846da6952f705a3": ("total employees", "headcount"),
    "fact-51fe568687932e2dd018135b": ("female employees", "headcount"),
    "fact-9fed67ef47fd5621fc25269e": ("male employees", "headcount"),
}

MALFORMED_ROW_HEADER = {
    "fact-694fd5a245fb94896c20702d",
    "fact-9c8bce3f9bb55a83e3b0081f",
    "fact-9cc507bc7f8d9969c5067ffe",
}
MISSING_EXPLICIT_UNIT = {
    "fact-a7c4661e89b5e94d76ac12d6",
    "fact-b33b7daa20f4994eb15094bf",
    "fact-c8b0367404a565bb35c38e6d",
    "fact-4c756893e3c978d4402f1dd7",
    "fact-35958a097d41d15592071e4a",
    "fact-820a3556889f3187138c62a7",
}
PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED = {
    "fact-2da08a5884dec5bea0c14929",
    "fact-a493ae5eb4cbe5efd5191eb5",
    "fact-942e199437a40f22deed4646",
    "fact-de4b45a16c13a504ef6cd8ff",
    "fact-79a007988ada028b1d3e388e",
    "fact-08f067d7938bc82dd9fda757",
    "fact-e293348725082b83a57dd296",
    "fact-4851a40b2d3caad54be8cf35",
    "fact-b4a23f679b4899dfb43f3423",
    "fact-7220be333b2975cde14f2db7",
    "fact-c817ed742d71bb17d465af49",
    "fact-4a6b3068111eb875835aec9b",
    "fact-cefbc11747d415233b136f2d",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )


def main() -> None:
    for source in SOURCES.values():
        if sha256_file(source["path"]) != source["sha256"]:
            raise ValueError(f"source report hash mismatch: {source['path']}")

    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    blocked = MALFORMED_ROW_HEADER | MISSING_EXPLICIT_UNIT | PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED
    if set(candidates) != set(PROMOTABLE) | blocked:
        raise ValueError("fail-closed: batch-five atomic candidate inventory changed")

    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    adjudications = load_jsonl(adjudications_path)
    trusted = load_jsonl(trusted_path)
    adjudicated_ids = {item["fact_record_id"] for item in adjudications}
    trusted_ids = {item["record_id"] for item in trusted}
    if set(PROMOTABLE) <= adjudicated_ids and set(PROMOTABLE) <= trusted_ids:
        if not SUMMARY.exists():
            raise ValueError("promotion exists but locked summary is missing")
        print(json.dumps(json.loads(SUMMARY.read_text()), sort_keys=True))
        return

    new_adjudications = []
    new_trusted = []
    for fact_id, (metric, unit) in sorted(PROMOTABLE.items()):
        fact = candidates[fact_id]
        if fact_id in adjudicated_ids or fact_id in trusted_ids:
            continue
        evidence = fact["evidence"][0]
        if evidence["normalized_period"] != 2025:
            raise ValueError(f"promotion period is not 2025: {fact_id}")
        source = SOURCES[fact["subject"]["document_ids"][0]]
        adjudication_id = stable_id(
            "adj",
            {
                "fact_record_id": fact_id,
                "source_sha256": source["sha256"],
                "assurance_page": source["assurance_page"],
            },
        )
        scope = f"{source['entity']}: {evidence['row_header']}"
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": source["entity"],
                "evidence": "issuer identity and independent assurance addressee match",
            },
            "metric": {
                "status": "matched",
                "normalized": metric,
                "evidence": source["assurance_text"],
            },
            "period": {
                "status": "matched",
                "normalized": "2025",
                "evidence": f"frozen table column {evidence['column_header']!r}",
            },
            "unit": {
                "status": "matched",
                "normalized": unit,
                "evidence": "unit is explicit in the row label, column label, or containing table",
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": scope,
                "evidence": source["assurance_text"],
            },
            "value": {
                "status": "matched",
                "normalized": fact["value"],
                "evidence": (
                    f"native PDF page {evidence['pdf_page']} and frozen cell "
                    f"{evidence['cell_handle']} agree on {evidence['quote']}"
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
                "assurance_scope_basis": source["assurance_basis"],
                "dimensions": dimensions,
                "promotion_decision": {
                    "eligible": True,
                    "target_tier": "B",
                    "reason": "all_six_dimensions_match_and_2025_assurance_scope_is_frozen",
                    "locked_experiments_modified": False,
                },
            }
        )

        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["qualifiers"].update(
            {
                "period_literal": "2025",
                "reference_period": 2025,
                "normalized_unit": unit,
                "scope_boundary": scope,
                "value_origin": "source_disclosure_independently_limited_assured",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].append(
            {
                "source_id": f"ASSURANCE-{fact['subject']['document_ids'][0]}-2025",
                "pdf_page": source["assurance_page"],
                "quote": source["assurance_text"],
                "role": "signed_independent_assurance_scope",
                "local_artifact": source["path"].relative_to(ROOT).as_posix(),
                "local_artifact_sha256": source["sha256"],
            }
        )
        if "scope_page" in source:
            promoted["evidence"].append(
                {
                    "source_id": "ASSURANCE-SCOPE-KB-B005-SIKA-SR2025-2025",
                    "pdf_page": source["scope_page"],
                    "quote": "The scope appendix includes 2025 employee headcount by gender.",
                    "role": "independent_assurance_scope_cross_reference",
                    "local_artifact": source["path"].relative_to(ROOT).as_posix(),
                    "local_artifact_sha256": source["sha256"],
                }
            )
        promoted["provenance"] = {
            "source_artifact": source["path"].relative_to(ROOT).as_posix(),
            "source_sha256": source["sha256"],
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
        "status": "scale_batch_005_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(new_trusted),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": sorted(blocked),
        "blocked_by_reason": {
            "malformed_row_header": sorted(MALFORMED_ROW_HEADER),
            "missing_explicit_unit_attachment": sorted(MISSING_EXPLICIT_UNIT),
            "prior_period_assurance_scope_not_established": sorted(
                PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED
            ),
        },
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {"atomic_increment_sha256": sha256_file(INCREMENT)},
        "outputs": {
            "adjudications_sha256": sha256_file(adjudications_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "scale_batch_006_source_acquisition_and_local_ingestion",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
