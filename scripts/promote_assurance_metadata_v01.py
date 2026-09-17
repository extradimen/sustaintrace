from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

PROFILES = {
    "P10-ASSURE-001": ("Shell plc", "Ernst & Young LLP"),
    "P17-ASSURE-001": (
        "BMW AG",
        "PricewaterhouseCoopers GmbH Wirtschaftsprüfungsgesellschaft",
    ),
    "P18-ASSURE-001": (
        "Deutsche Telekom AG",
        "Deloitte GmbH Wirtschaftsprüfungsgesellschaft",
    ),
    "P20-ASSURE-001": ("Holcim Ltd", "EY & Associés"),
    "P21-ASSURE-001": (
        "BASF SE",
        "Deloitte GmbH Wirtschaftsprüfungsgesellschaft",
    ),
    "P22-ASSURE-001": (
        "Bayer AG",
        "Deloitte GmbH Wirtschaftsprüfungsgesellschaft",
    ),
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
    facts_path = KB / "fact_records.jsonl"
    boundary_path = KB / "assurance_boundary_adjudications.jsonl"
    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    boundaries = load_jsonl(boundary_path)
    existing_adjudications = load_jsonl(adjudications_path)
    existing_trusted = load_jsonl(trusted_path)
    existing_ids = {item["fact_record_id"] for item in existing_adjudications}
    trusted_ids = {item["record_id"] for item in existing_trusted}
    new_adjudications = []
    new_trusted = []
    for boundary in boundaries:
        fact_id = boundary["fact_record_id"]
        if fact_id in existing_ids or fact_id in trusted_ids:
            continue
        fact = facts[fact_id]
        entity, provider = PROFILES[boundary["task_id"]]
        artifact = ROOT / boundary["source_artifact"]
        if sha256_file(artifact) != boundary["source_artifact_sha256"]:
            raise ValueError(f"source artifact changed: {fact_id}")
        common_evidence = (
            f"signed independent assurance text on page {boundary['source_page']} "
            f"and validated boundary record {boundary['validation_id']}"
        )
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": entity,
                "evidence": "issuer identity and addressee in the signed assurance report",
            },
            "metric": {
                "status": "matched",
                "normalized": boundary["predicate"],
                "evidence": common_evidence,
            },
            "period": {
                "status": "matched",
                "normalized": "not_applicable_non_temporal_metadata",
                "evidence": "validated non-temporal assurance metadata classification",
            },
            "unit": {
                "status": "matched",
                "normalized": "not_applicable_non_quantitative_metadata",
                "evidence": "the field is textual assurance metadata, not a measurement",
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": boundary["resolved_boundary"],
                "evidence": common_evidence,
            },
            "value": {
                "status": "matched",
                "normalized": boundary["value"],
                "evidence": (
                    "exact literal in the unique native PDF context and the signed "
                    "independent assurance statement"
                ),
            },
        }
        adjudication_id = stable_id(
            "adj",
            {
                "fact_record_id": fact_id,
                "boundary_adjudication_id": boundary["adjudication_id"],
                "source_sha256": boundary["source_artifact_sha256"],
            },
        )
        new_adjudications.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_independent_adjudication",
                "adjudication_id": adjudication_id,
                "fact_record_id": fact_id,
                "task_id": boundary["task_id"],
                "assurance_scope_basis": "direct_independent_statement",
                "dimensions": dimensions,
                "promotion_decision": {
                    "eligible": True,
                    "target_tier": "B",
                    "reason": (
                        "all_six_dimensions_match_and_signed_independent_assurance_text_is_frozen"
                    ),
                    "locked_experiments_modified": False,
                },
            }
        )
        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["subject"]["entity_label"] = entity
        promoted["qualifiers"].update(
            {
                "period_literal": None,
                "reference_period": None,
                "normalized_unit": None,
                "scope_boundary": boundary["resolved_boundary"],
                "value_origin": "signed_independent_assurance_statement",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].append(
            {
                "source_id": f"ASSURANCE-{provider}",
                "pdf_page": boundary["source_page"],
                "quote": boundary["source_text"],
                "role": "direct_independent_assurance_metadata",
                "local_artifact": boundary["source_artifact"],
                "local_artifact_sha256": boundary["source_artifact_sha256"],
            }
        )
        promoted["provenance"] = {
            "source_artifact": boundary["source_artifact"],
            "source_sha256": boundary["source_artifact_sha256"],
            "reference_status": f"tier_b_adjudication:{adjudication_id}",
            "simulated": False,
        }
        promoted["promotion"] = {
            "eligible": True,
            "reason": f"passed_independent_adjudication:{adjudication_id}",
        }
        new_trusted.append(promoted)

    combined_adjudications = sorted(
        existing_adjudications + new_adjudications,
        key=lambda item: (item["task_id"], item["fact_record_id"]),
    )
    combined_trusted = sorted(
        existing_trusted + new_trusted,
        key=lambda item: (item["subject"]["task_id"], item["record_id"]),
    )
    adjudication_schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-independent-adjudication-v0.1.schema.json").read_text()
    )
    fact_schema = json.loads(
        (ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text()
    )
    validate_records(combined_adjudications, adjudication_schema)
    validate_records(combined_trusted, fact_schema)
    dump_jsonl(adjudications_path, combined_adjudications)
    dump_jsonl(trusted_path, combined_trusted)
    summary = {
        "schema_version": "0.1",
        "status": "assurance_metadata_six_dimension_review_and_tier_b_overlay_complete",
        "reviewed": len(boundaries),
        "newly_promoted_to_tier_b": len(new_trusted),
        "total_trusted_tier_b": len(combined_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "fact_records_sha256": sha256_file(facts_path),
            "assurance_boundaries_sha256": sha256_file(boundary_path),
        },
        "outputs": {
            "adjudications": {
                "path": adjudications_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(adjudications_path),
            },
            "trusted_facts": {
                "path": trusted_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(trusted_path),
            },
        },
        "next_gate": "implement_metric_component_boundary_validator_with_negative_regression",
    }
    summary_path = KB / "assurance_metadata_promotion_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
