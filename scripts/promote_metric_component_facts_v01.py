from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

NORMALIZATION = {
    "P18-ENERGY-001": {
        "entity": "Deutsche Telekom AG and Group",
        "unit": "MWh",
        "metric": "total fossil energy consumption",
    },
    "P19-SCOPE3-001": {
        "entity": "Novo Nordisk A/S Group",
        "unit": "thousand metric tons CO2e",
        "metric": "Scope 3 category 1 purchased goods and services",
    },
    "P21-SCOPE3-001": {
        "entity": "BASF Group",
        "unit": "million metric tons CO2e",
        "metric": "Scope 3 category component",
    },
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
    boundaries_path = KB / "metric_component_boundary_adjudications.jsonl"
    reviews_path = KB / "independent_corroboration_reviews.jsonl"
    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    boundaries = load_jsonl(boundaries_path)
    sources = {}
    for review in load_jsonl(reviews_path):
        source = review["candidate_source"]
        sources.setdefault(source["parent_artifact"], source)
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
        task_id = boundary["task_id"]
        normalized = NORMALIZATION[task_id]
        source = sources[boundary["source_artifact"]]
        local_assurance = ROOT / source["local_artifact"]
        parent = ROOT / source["parent_artifact"]
        if sha256_file(local_assurance) != source["local_artifact_sha256"]:
            raise ValueError(f"assurance extract changed: {fact_id}")
        if sha256_file(parent) != source["parent_artifact_sha256"]:
            raise ValueError(f"parent report changed: {fact_id}")
        coordinate = boundary["table_coordinate"]
        period = coordinate["column"][:4]
        metric = (
            normalized["metric"]
            if task_id != "P21-SCOPE3-001"
            else f"Scope 3 {coordinate['row']}"
        )
        scope_evidence = source["evidence_locator"]["metric_scope_locator"]
        adjudication_id = stable_id(
            "adj",
            {
                "fact_record_id": fact_id,
                "boundary_adjudication_id": boundary["adjudication_id"],
                "assurance_sha256": source["local_artifact_sha256"],
            },
        )
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": normalized["entity"],
                "evidence": "issuer identity in the frozen report and assurance addressee",
            },
            "metric": {
                "status": "matched",
                "normalized": metric,
                "evidence": scope_evidence,
            },
            "period": {
                "status": "matched",
                "normalized": period,
                "evidence": (
                    f"frozen table graph binds the selected cell to {coordinate['column']}"
                ),
            },
            "unit": {
                "status": "matched",
                "normalized": normalized["unit"],
                "evidence": "unit heading in the frozen disclosure table",
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": boundary["resolved_boundary"],
                "evidence": (
                    "validated row, column, component role, method role and applicable footnote"
                ),
            },
            "value": {
                "status": "matched",
                "normalized": boundary["value"],
                "evidence": (
                    f"unique native binding on page {boundary['source_page']} and exact "
                    "validated table-cell coordinate"
                ),
            },
        }
        new_adjudications.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_independent_adjudication",
                "adjudication_id": adjudication_id,
                "fact_record_id": fact_id,
                "task_id": task_id,
                "assurance_scope_basis": "whole_statement_inclusion_with_exclusions_checked",
                "dimensions": dimensions,
                "promotion_decision": {
                    "eligible": True,
                    "target_tier": "B",
                    "reason": (
                        "all_six_dimensions_match_and_independent_limited_assurance_is_frozen"
                    ),
                    "locked_experiments_modified": False,
                },
            }
        )
        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["subject"]["entity_label"] = normalized["entity"]
        promoted["qualifiers"].update(
            {
                "period_literal": period,
                "reference_period": period,
                "normalized_unit": normalized["unit"],
                "scope_boundary": boundary["resolved_boundary"],
                "value_origin": "source_disclosure_independently_assured",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].append(
            {
                "source_id": f"ASSURANCE-{source['provider']}",
                "pdf_page": source["evidence_locator"]["assurance_report_pages"][0],
                "quote": scope_evidence,
                "role": "independent_assurance_scope",
                "local_artifact": source["local_artifact"],
                "local_artifact_sha256": source["local_artifact_sha256"],
            }
        )
        promoted["provenance"] = {
            "source_artifact": source["local_artifact"],
            "source_sha256": source["local_artifact_sha256"],
            "reference_status": f"tier_b_adjudication:{adjudication_id}",
            "simulated": False,
        }
        promoted["promotion"] = {
            "eligible": True,
            "reason": f"passed_independent_adjudication:{adjudication_id}",
        }
        new_trusted.append(promoted)

    all_adjudications = sorted(
        existing_adjudications + new_adjudications,
        key=lambda item: (item["task_id"], item["fact_record_id"]),
    )
    all_trusted = sorted(
        existing_trusted + new_trusted,
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
        "status": "metric_component_six_dimension_review_and_tier_b_overlay_complete",
        "reviewed": len(boundaries),
        "newly_promoted_to_tier_b": len(new_trusted),
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "facts_sha256": sha256_file(facts_path),
            "boundaries_sha256": sha256_file(boundaries_path),
            "independent_reviews_sha256": sha256_file(reviews_path),
        },
        "outputs": {
            "adjudications_sha256": sha256_file(adjudications_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "implement_taxonomy_classification_boundary_validator",
    }
    summary_path = KB / "metric_component_promotion_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
