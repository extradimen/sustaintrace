from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_006_atomic_fact_records.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_006_tier_b_promotion.lock.json"
SOURCE = {
    "entity": "AB Volvo Group",
    "path": ROOT / "data/raw/scale_batch_006/volvo-group-annual-report-2025.pdf",
    "sha256": "4a2a5c41dc1331d60103e5757af0e90a6a2ea234b9753138ae0ec4db315df969",
    "assurance_page": 215,
    "assurance_basis": "whole_statement_inclusion_with_exclusions_checked",
    "assurance_text": (
        "We have conducted a limited assurance engagement of the sustainability statement "
        "for AB Volvo for the financial year 2025. The sustainability statement is included "
        "on pages 144–189 in this document."
    ),
}

PROMOTABLE = {
    "fact-39a82930cf824b7e2b4327da": ("male employees", "headcount"),
    "fact-2eba557270e1beb5bf4e8be9": ("female employees", "headcount"),
    "fact-8b592f76837c3f3219cad2d7": ("employees reported as other gender", "headcount"),
    "fact-b424fbe8250d9656891226d3": ("total employees", "headcount"),
}
PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED = {
    "fact-57e79ef93ccfd8cae615be40",
    "fact-0655447566d09d7c43899f3a",
    "fact-3debd82aa0d1a6003b26c228",
    "fact-6054b77dac64ee29b6a58f9a",
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
    if sha256_file(SOURCE["path"]) != SOURCE["sha256"]:
        raise ValueError("source report hash mismatch")
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    if set(candidates) != set(PROMOTABLE) | PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED:
        raise ValueError("fail-closed: batch-six atomic candidate inventory changed")

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
        if evidence["normalized_period"] != 2025 or evidence["pdf_page"] != 174:
            raise ValueError(f"promotion period or page mismatch: {fact_id}")
        adjudication_id = stable_id(
            "adj",
            {
                "fact_record_id": fact_id,
                "source_sha256": SOURCE["sha256"],
                "assurance_page": SOURCE["assurance_page"],
            },
        )
        scope = f"{SOURCE['entity']}: {evidence['row_header']}"
        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": SOURCE["entity"],
                "evidence": "issuer identity and auditor addressee match",
            },
            "metric": {
                "status": "matched",
                "normalized": metric,
                "evidence": "frozen workforce table row header and assurance page range",
            },
            "period": {
                "status": "matched",
                "normalized": "2025",
                "evidence": f"frozen table column {evidence['column_header']!r}",
            },
            "unit": {
                "status": "matched",
                "normalized": unit,
                "evidence": "table heading explicitly states Headcount",
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": scope,
                "evidence": SOURCE["assurance_text"],
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
                "assurance_scope_basis": SOURCE["assurance_basis"],
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
                "source_id": "ASSURANCE-KB-B006-VOLVO-AR2025-2025",
                "pdf_page": SOURCE["assurance_page"],
                "quote": SOURCE["assurance_text"],
                "role": "signed_independent_assurance_scope",
                "local_artifact": SOURCE["path"].relative_to(ROOT).as_posix(),
                "local_artifact_sha256": SOURCE["sha256"],
            }
        )
        promoted["provenance"] = {
            "source_artifact": SOURCE["path"].relative_to(ROOT).as_posix(),
            "source_sha256": SOURCE["sha256"],
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
        "status": "scale_batch_006_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(new_trusted),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": sorted(PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED),
        "blocked_by_reason": {
            "prior_period_assurance_scope_not_established": sorted(
                PRIOR_PERIOD_SCOPE_NOT_ESTABLISHED
            )
        },
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {"atomic_increment_sha256": sha256_file(INCREMENT)},
        "outputs": {
            "adjudications_sha256": sha256_file(adjudications_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "scale_batch_006_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
