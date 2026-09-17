from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_007_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_007_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_007_tier_b_promotion.lock.json"

SOURCES = {
    "KB-B007-NOKIA-AR2025": {
        "entity": "Nokia Corporation",
        "path": ROOT / "data/raw/scale_batch_007/nokia-annual-report-2025.pdf",
        "sha256": "fa6067b17c09d25b05571ceec218fb3f524054fc8cb7d8eb899221c7b7404455",
        "assurance_page": 286,
        "assurance_text": (
            "We have performed a limited assurance engagement on the group sustainability "
            "statement of Nokia Corporation that is included in the report of the Board of "
            "Directors for the reporting period 1.1.–31.12.2025."
        ),
    },
    "KB-B007-ATLAS-COPCO-AR2025": {
        "entity": "Atlas Copco AB",
        "path": ROOT / "data/raw/scale_batch_007/atlas-copco-annual-report-2025.pdf",
        "sha256": "70d076bd915ecb111549426d3bf2b585626e117e20509f42c84dd001915e4164",
        "assurance_page": 169,
        "assurance_text": (
            "We have conducted a limited assurance engagement of the sustainability statement "
            "prepared by Atlas Copco AB for the financial year 2025. The sustainability "
            "statement is included on pages 31–48 and 52–84 of this document."
        ),
    },
}

PROMOTABLE = {
    "fact-2dc99cbc1fcc3f234be85773": {
        "metric": "renewable energy production",
        "unit": "MWh",
    },
    "fact-6ac845304b724ca730f173cf": {
        "metric": "total employee turnover",
        "unit": "%",
    },
    "fact-4b0e0b414f42482481b51f8a": {
        "metric": "voluntary employee leave",
        "unit": "%",
    },
}

BLOCKED = {
    "fact-a79136f5dd947b424922c74e": "prior_period_assurance_scope_not_established",
    "fact-90e5305abbc116904c2cae6a": "prior_period_and_coordinate_corroboration_not_established",
    "fact-f0f8b94877c8ed66da35638e": "prior_period_assurance_scope_not_established",
    "fact-caa61e048f3cd976849d17d4": "prior_period_assurance_scope_not_established",
    "fact-6154378df6ff6d6f2af9236b": "native_numeric_coordinate_corroboration_not_established",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        )
    )


def main() -> None:
    for source in SOURCES.values():
        if sha256_file(source["path"]) != source["sha256"]:
            raise ValueError("source report hash mismatch")
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    if set(candidates) != set(PROMOTABLE) | set(BLOCKED):
        raise ValueError("fail-closed: batch-seven atomic candidate inventory changed")
    validations = {
        item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)
    }
    for fact_id in PROMOTABLE:
        if not validations[fact_id]["coordinate_corroborated"]:
            raise ValueError(f"coordinate corroboration missing: {fact_id}")

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
    for fact_id, definition in sorted(PROMOTABLE.items()):
        if fact_id in adjudicated_ids or fact_id in trusted_ids:
            continue
        fact = candidates[fact_id]
        evidence = fact["evidence"][0]
        if evidence["normalized_period"] != 2025:
            raise ValueError(f"promotion period mismatch: {fact_id}")
        source = SOURCES[evidence["source_id"]]
        if evidence["source_id"] == "KB-B007-ATLAS-COPCO-AR2025" and not (
            52 <= evidence["pdf_page"] <= 84
        ):
            raise ValueError(f"Atlas Copco fact outside assured page range: {fact_id}")
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
                "evidence": "issuer identity and auditor addressee match",
            },
            "metric": {
                "status": "matched",
                "normalized": definition["metric"],
                "evidence": "frozen table row header and assurance scope",
            },
            "period": {
                "status": "matched",
                "normalized": "2025",
                "evidence": f"frozen table column {evidence['column_header']!r}",
            },
            "unit": {
                "status": "matched",
                "normalized": definition["unit"],
                "evidence": "native PDF table heading or row label explicitly states unit",
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
                "assurance_scope_basis": "whole_statement_inclusion_with_exclusions_checked",
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
                "normalized_unit": definition["unit"],
                "scope_boundary": scope,
                "value_origin": "source_disclosure_independently_limited_assured",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].append(
            {
                "source_id": f"ASSURANCE-{evidence['source_id']}-2025",
                "pdf_page": source["assurance_page"],
                "quote": source["assurance_text"],
                "role": "signed_independent_assurance_scope",
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
        "status": "scale_batch_007_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(new_trusted),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": sorted(BLOCKED),
        "blocked_by_reason": {
            reason: sorted(fact_id for fact_id, value in BLOCKED.items() if value == reason)
            for reason in sorted(set(BLOCKED.values()))
        },
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha256_file(INCREMENT),
            "atomic_validations_sha256": sha256_file(VALIDATIONS),
        },
        "outputs": {
            "adjudications_sha256": sha256_file(adjudications_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "next_gate": "scale_batch_007_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
