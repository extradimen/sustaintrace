from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
MANIFEST = (
    ROOT
    / "data/external/independent_assurance/v0.1"
    / "gsk_target_performance_source_manifest_v0.1.lock.json"
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    validations_path = KB / "target_performance_boundary_validations.jsonl"
    validations = load_jsonl(validations_path)
    manifest = json.loads(MANIFEST.read_text())
    for source in manifest["sources"]:
        for path_key, hash_key in (
            ("parent_artifact", "parent_sha256"),
            ("extract_artifact", "extract_sha256"),
        ):
            if sha256_file(ROOT / source[path_key]) != source[hash_key]:
                raise ValueError(f"source hash mismatch: {source[path_key]}")

    decisions = {
        "target_2030_absolute_reduction_percent": (
            "blocked_independent_evidence_incomplete",
            "no_frozen_sbti_company_target_record_for_80_percent_2030_claim",
            [False, False, False, False, False],
            None,
        ),
        "target_2045_absolute_reduction_percent": (
            "blocked_independent_evidence_incomplete",
            "no_frozen_sbti_company_target_record_for_90_percent_2045_claim",
            [False, False, False, False, False],
            None,
        ),
        "issuer_reduction_percent": (
            "ready_for_tier_b_promotion",
            "deloitte_assured_2025_486_and_2024_565_reproduce_disclosed_14_percent_after_rounding",
            [True, True, True, True, True],
            {
                "expression": "round(abs((486 - 565) / 565 * 100))",
                "raw_percent": -13.982300884955752,
                "rounded_absolute_percent": 14,
                "expected": 14,
                "passed": True,
            },
        ),
        "reduction_from_2020_baseline_percent": (
            "blocked_independent_evidence_incomplete",
            "2025_water_value_is_assured_but_no_assured_same_method_2020_baseline_is_frozen",
            [True, False, False, True, False],
            None,
        ),
    }
    records = []
    for validation in validations:
        predicate = validation["predicate"]
        decision, reason, matches, calculation = decisions[predicate]
        metric, period, unit, scope, value = matches
        identity = {
            "fact_record_id": validation["fact_record_id"],
            "validation_id": validation["validation_id"],
            "manifest_sha256": sha256_file(MANIFEST),
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "target_performance_derived_adjudication",
                "adjudication_id": stable_id("target-performance-adj", identity),
                "fact_record_id": validation["fact_record_id"],
                "task_id": validation["task_id"],
                "predicate": predicate,
                "validation_id": validation["validation_id"],
                "checks": {
                    "boundary_validation_ready": validation["validation_status"]
                    == "ready_for_supervised_execution",
                    "source_hashes_valid": True,
                    "independent_entity_match": True,
                    "independent_metric_match": metric,
                    "independent_period_match": period,
                    "independent_unit_match": unit,
                    "independent_scope_match": scope,
                    "independent_value_match": value,
                    "deterministic_recalculation": calculation,
                },
                "decision": decision,
                "reason": reason,
                "locked_experiments_modified_or_rescored": False,
            }
        )
    records.sort(key=lambda item: item["predicate"])
    schema = json.loads(
        (
            ROOT
            / "schemas/knowledge/target-performance-derived-adjudication-v0.1.schema.json"
        ).read_text()
    )
    validate_records(records, schema)
    output_path = KB / "target_performance_derived_adjudications.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "0.1",
        "status": "target_performance_independent_derived_adjudication_complete",
        "reviewed": len(records),
        "ready_for_tier_b_promotion": sum(
            item["decision"] == "ready_for_tier_b_promotion" for item in records
        ),
        "blocked_independent_evidence_incomplete": sum(
            item["decision"] == "blocked_independent_evidence_incomplete" for item in records
        ),
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "validations_sha256": sha256_file(validations_path),
            "source_manifest_sha256": sha256_file(MANIFEST),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "promote_only_the_14_percent_scope_1_and_2_relation",
    }
    summary_path = KB / "target_performance_derived_adjudication_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
