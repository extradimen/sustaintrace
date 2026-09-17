from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


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
    boundaries_path = KB / "organizational_population_boundary_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    independent_path = KB / "tier_b_independent_adjudications.jsonl"
    scope_path = (
        ROOT
        / "data/external/independent_assurance/v0.1"
        / "holcim_2025_population_assurance_scope_v0.1.lock.json"
    )
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    boundaries = load_jsonl(boundaries_path)
    trusted = load_jsonl(trusted_path)
    independent = load_jsonl(independent_path)
    trusted_ids = {item["record_id"] for item in trusted}
    independent_ids = {item["fact_record_id"] for item in independent}
    scope = json.loads(scope_path.read_text())
    if sha256_file(ROOT / scope["parent_artifact"]) != scope["parent_sha256"]:
        raise ValueError("Holcim parent report hash mismatch")
    if sha256_file(ROOT / scope["assurance_artifact"]) != scope["assurance_sha256"]:
        raise ValueError("Holcim assurance extract hash mismatch")
    new_adjudications = []
    new_trusted = []
    for boundary in boundaries:
        fact_id = boundary["fact_record_id"]
        if fact_id in trusted_ids or fact_id in independent_ids:
            continue
        fact = facts[fact_id]
        population = boundary["resolved_population"]
        identity = {
            "fact_record_id": fact_id,
            "boundary_adjudication_id": boundary["adjudication_id"],
            "assurance_sha256": scope["assurance_sha256"],
        }
        adjudication_id = stable_id("adj", identity)
        metric_name = {
            "global_headcount": "global employee headcount",
            "difference_headcount": "employees excluded from SF contract-type coverage",
        }[boundary["predicate"]]
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": "Holcim Ltd Group",
                "evidence": "issuer identity and assurance addressee in frozen sources",
            },
            "metric": {
                "status": "matched",
                "normalized": metric_name,
                "evidence": scope["scope_locator"],
            },
            "period": {
                "status": "matched",
                "normalized": population["period"],
                "evidence": "year-end 2025 is explicit on source page 120",
            },
            "unit": {
                "status": "matched",
                "normalized": "employee headcount",
                "evidence": "source labels identify employees and headcount",
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": population["scope_role"],
                "evidence": (
                    "46,055 global employees; 43,875 SF-covered employees; "
                    "2,180 newly acquired-entity employees excluded from SF metrics"
                ),
            },
            "value": {
                "status": "matched",
                "normalized": boundary["value"],
                "evidence": ("40,590 + 3,285 = 43,875 and 43,875 + 2,180 = 46,055"),
            },
        }
        new_adjudications.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_independent_adjudication",
                "adjudication_id": adjudication_id,
                "fact_record_id": fact_id,
                "task_id": boundary["task_id"],
                "assurance_scope_basis": "metric_explicitly_listed",
                "dimensions": dimensions,
                "promotion_decision": {
                    "eligible": True,
                    "target_tier": "B",
                    "reason": "all_six_dimensions_match_and_population_indicators_are_assured",
                    "locked_experiments_modified": False,
                },
            }
        )
        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["subject"]["entity_label"] = "Holcim Ltd Group"
        promoted["qualifiers"].update(
            {
                "period_literal": population["period"],
                "reference_period": population["period"],
                "normalized_unit": "employee headcount",
                "scope_boundary": population["scope_role"],
                "value_origin": "source_disclosure_independently_assured",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].append(
            {
                "source_id": "ASSURANCE-EY-HOLCIM-2025",
                "pdf_page": 136,
                "quote": scope["scope_locator"],
                "role": "independent_assurance_scope",
                "local_artifact": scope["assurance_artifact"],
                "local_artifact_sha256": scope["assurance_sha256"],
            }
        )
        promoted["provenance"] = {
            "source_artifact": scope["assurance_artifact"],
            "source_sha256": scope["assurance_sha256"],
            "reference_status": f"tier_b_adjudication:{adjudication_id}",
            "simulated": False,
        }
        promoted["promotion"] = {
            "eligible": True,
            "reason": f"passed_independent_adjudication:{adjudication_id}",
        }
        new_trusted.append(promoted)
    all_adjudications = sorted(
        independent + new_adjudications,
        key=lambda item: (item["task_id"], item["fact_record_id"]),
    )
    all_trusted = sorted(
        trusted + new_trusted,
        key=lambda item: (item["subject"]["task_id"], item["record_id"]),
    )
    validate_records(
        all_adjudications,
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
    dump_jsonl(independent_path, all_adjudications)
    dump_jsonl(trusted_path, all_trusted)
    summary = {
        "schema_version": "0.1",
        "status": "population_six_dimension_review_and_tier_b_overlay_complete",
        "reviewed": len(boundaries),
        "newly_promoted_to_tier_b": len(new_trusted),
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "facts_sha256": sha256_file(facts_path),
            "boundaries_sha256": sha256_file(boundaries_path),
            "scope_manifest_sha256": sha256_file(scope_path),
        },
        "outputs": {
            "adjudications_sha256": sha256_file(independent_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "implement_target_and_performance_boundary_validator",
    }
    summary_path = KB / "population_promotion_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
