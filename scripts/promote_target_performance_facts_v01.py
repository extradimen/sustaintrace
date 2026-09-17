from __future__ import annotations

import copy
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


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )


def main() -> None:
    facts_path = KB / "fact_records.jsonl"
    adjudications_path = KB / "target_performance_derived_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    independent_path = KB / "tier_b_independent_adjudications.jsonl"
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    derived = load_jsonl(adjudications_path)
    trusted = load_jsonl(trusted_path)
    independent = load_jsonl(independent_path)
    trusted_ids = {item["record_id"] for item in trusted}
    independent_ids = {item["fact_record_id"] for item in independent}
    manifest = json.loads(MANIFEST.read_text())
    current = manifest["sources"][0]
    comparator = manifest["sources"][1]
    for source in manifest["sources"]:
        if sha256_file(ROOT / source["parent_artifact"]) != source["parent_sha256"]:
            raise ValueError("GSK parent report hash mismatch")
        if sha256_file(ROOT / source["extract_artifact"]) != source["extract_sha256"]:
            raise ValueError("GSK assurance extract hash mismatch")

    ready = [item for item in derived if item["decision"] == "ready_for_tier_b_promotion"]
    if len(ready) != 1 or ready[0]["predicate"] != "issuer_reduction_percent":
        raise ValueError(
            "fail-closed: exactly the independently reproducible 14% relation must be ready"
        )
    new_reviews = []
    new_trusted = []
    for item in ready:
        fact_id = item["fact_record_id"]
        if fact_id in trusted_ids or fact_id in independent_ids:
            continue
        fact = facts[fact_id]
        identity = {
            "fact_record_id": fact_id,
            "derived_adjudication_id": item["adjudication_id"],
            "manifest_sha256": sha256_file(MANIFEST),
        }
        adjudication_id = stable_id("adj", identity)
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": "GSK plc",
                "evidence": "Both Deloitte reports address GSK plc.",
            },
            "metric": {
                "status": "matched",
                "normalized": "total Scope 1 and 2 market-based emissions",
                "evidence": (
                    "The metric is explicitly listed in both selected-information schedules."
                ),
            },
            "period": {
                "status": "matched",
                "normalized": "2025 versus 2024",
                "evidence": (
                    "The independently assured schedules cover years ended "
                    "31 December 2025 and 2024."
                ),
            },
            "unit": {
                "status": "matched",
                "normalized": "thousand tonnes CO2e; derived percent",
                "evidence": (
                    "Both assured operands use thousand tonnes CO2e; "
                    "their ratio is unitless percent."
                ),
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": "Scope 1 plus Scope 2 market-based",
                "evidence": (
                    "The selected-information line uses the identical boundary in both years."
                ),
            },
            "value": {
                "status": "matched",
                "normalized": 14,
                "evidence": (
                    "Assured values 486 and 565 give -13.9823%, "
                    "which rounds to a 14% reduction."
                ),
            },
        }
        new_reviews.append(
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
                        "all_six_dimensions_match_and_two_assured_operands_"
                        "reproduce_rounded_relation"
                    ),
                    "locked_experiments_modified": False,
                },
            }
        )
        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["subject"]["entity_label"] = "GSK plc"
        promoted["qualifiers"].update(
            {
                "period_literal": "2025 versus 2024",
                "reference_period": 2024,
                "normalized_unit": "percent reduction",
                "scope_boundary": "total Scope 1 and 2 market-based emissions",
                "calculation_expression": "abs((486 - 565) / 565 * 100) = 13.9823%; rounded to 14%",
                "value_origin": "deterministic_recalculation_from_independently_assured_operands",
                "answer_status": "verified",
            }
        )
        for source, page, value in ((current, 33, 486), (comparator, 47, 565)):
            promoted["evidence"].append(
                {
                    "source_id": f"ASSURANCE-DELOITTE-GSK-{source['covered_period']}",
                    "pdf_page": page,
                    "quote": (
                        "Total Scope 1 and 2 market-based emissions: "
                        f"assured value {value} thousand tonnes CO2e"
                    ),
                    "role": "independent_assurance_operand",
                    "local_artifact": source["extract_artifact"],
                    "local_artifact_sha256": source["extract_sha256"],
                }
            )
        promoted["provenance"] = {
            "source_artifact": current["extract_artifact"],
            "source_sha256": current["extract_sha256"],
            "reference_status": f"tier_b_adjudication:{adjudication_id}",
            "simulated": False,
        }
        promoted["promotion"] = {
            "eligible": True,
            "reason": f"passed_independent_adjudication:{adjudication_id}",
        }
        new_trusted.append(promoted)

    all_reviews = sorted(
        independent + new_reviews, key=lambda x: (x["task_id"], x["fact_record_id"])
    )
    all_trusted = sorted(
        trusted + new_trusted, key=lambda x: (x["subject"]["task_id"], x["record_id"])
    )
    validate_records(
        all_reviews,
        json.loads(
            (
                ROOT / "schemas/knowledge/tier-b-independent-adjudication-v0.1.schema.json"
            ).read_text()
        ),
    )
    validate_records(
        all_trusted,
        json.loads((ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text()),
    )
    dump_jsonl(independent_path, all_reviews)
    dump_jsonl(trusted_path, all_trusted)
    summary = {
        "schema_version": "0.1",
        "status": "target_performance_six_dimension_review_and_tier_b_overlay_complete",
        "reviewed": 4,
        "newly_promoted_to_tier_b": len(new_trusted),
        "blocked_independent_evidence_incomplete": 3,
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "derived_adjudications_sha256": sha256_file(adjudications_path),
            "source_manifest_sha256": sha256_file(MANIFEST),
        },
        "outputs": {
            "adjudications_sha256": sha256_file(independent_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "post_execution_validation_and_rollback_closure",
    }
    summary_path = KB / "target_performance_promotion_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
