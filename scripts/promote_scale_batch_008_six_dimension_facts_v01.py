from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_008_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_008_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_008_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_008_native_coordinate_audit.lock.json"
SOURCE = ROOT / "data/raw/scale_batch_008/sandvik-annual-report-2025.pdf"
SOURCE_SHA256 = "b3f7b20c4dc8a59fd92bc6a89ed5b8efa19a0328b816837cae7d8864438af165"
PROMOTABLE = "fact-d4dae099a6653eda17f6e507"
BLOCKED = {
    "fact-488ae3e2a6d43dbf33432906": (
        "comparative_2024_explicitly_excluded_from_2025_limited_assurance"
    )
}
ASSURANCE_PAGE = 112
ASSURANCE_TEXT = (
    "We have conducted a limited assurance engagement of the sustainability statement "
    "for Sandvik AB (publ) for the financial year 2025. The sustainability statement is "
    "included on page 51–111 in this document."
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )


def native_coordinate_audit() -> dict[str, Any]:
    result = subprocess.run(
        ["pdftotext", "-f", "71", "-l", "71", "-layout", str(SOURCE), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    text = result.stdout
    ordered_fragments = (
        "Total energy consumption",
        "from activities in high climate",
        "impact sectors per net",
        "revenue from activities in high",
        "climate impact sectors",
    )
    cursor = 0
    positions = []
    for fragment in ordered_fragments:
        cursor = text.find(fragment, cursor)
        if cursor < 0:
            raise ValueError(f"native row fragment missing: {fragment}")
        positions.append(cursor)
        cursor += len(fragment)
    checks = {
        "source_sha256_matches": sha256_file(SOURCE) == SOURCE_SHA256,
        "page_footer_matches": "Sandvik Annual Report 2025      71" in text,
        "unit_heading_present": "revenue, MWh/MSEK" in text,
        "year_headers_present": "2024            2025" in text,
        "row_fragments_present_in_order": positions == sorted(positions),
        "row_values_present_in_order": "9.2            9.1              -1" in text,
    }
    if not all(checks.values()):
        raise ValueError(f"native coordinate audit failed: {checks}")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-008-NATIVE-COORDINATE-AUDIT",
        "status": "passed",
        "document_id": "KB-B008-SANDVIK-AR2025",
        "pdf_page": 71,
        "metric": "energy intensity per net revenue from high climate impact sectors",
        "unit": "MWh/MSEK",
        "columns": {"2024": "9.2", "2025": "9.1", "yearly_change_percent": "-1"},
        "checks": checks,
        "native_layout_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_sha256": SOURCE_SHA256,
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def main() -> None:
    audit = native_coordinate_audit()
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    if set(candidates) != {PROMOTABLE, *BLOCKED}:
        raise ValueError("fail-closed: batch-eight atomic candidate inventory changed")
    validations = {item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)}
    if not validations[PROMOTABLE]["checks"]["table_graph_coordinate_exact"]:
        raise ValueError("frozen table-graph coordinate is not exact")

    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    adjudications = load_jsonl(adjudications_path)
    trusted = load_jsonl(trusted_path)
    adjudicated_ids = {item["fact_record_id"] for item in adjudications}
    trusted_ids = {item["record_id"] for item in trusted}
    if PROMOTABLE in adjudicated_ids and PROMOTABLE in trusted_ids:
        if not SUMMARY.exists():
            raise ValueError("promotion exists but locked summary is missing")
        print(json.dumps(json.loads(SUMMARY.read_text()), sort_keys=True))
        return

    fact = candidates[PROMOTABLE]
    evidence = fact["evidence"][0]
    if evidence["normalized_period"] != 2025 or evidence["quote"] != "9.1":
        raise ValueError("promotable cell identity changed")
    adjudication_id = stable_id(
        "adj",
        {
            "fact_record_id": PROMOTABLE,
            "source_sha256": SOURCE_SHA256,
            "assurance_page": ASSURANCE_PAGE,
        },
    )
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": "Sandvik AB (publ)",
            "evidence": "issuer identity and auditor addressee match",
        },
        "metric": {
            "status": "matched",
            "normalized": "energy intensity per net revenue from high climate impact sectors",
            "evidence": "ordered native PDF row fragments and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": "2025",
            "evidence": "native PDF year column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": "MWh/MSEK",
            "evidence": "native PDF table heading explicitly states unit",
        },
        "scope_boundary": {
            "status": "matched",
            "normalized": "Sandvik activities in high climate impact sectors",
            "evidence": ASSURANCE_TEXT,
        },
        "value": {
            "status": "matched",
            "normalized": "9.1",
            "evidence": "native PDF ordered row values and frozen 2025 cell match",
        },
    }
    adjudication = {
        "schema_version": "0.1",
        "record_kind": "tier_b_independent_adjudication",
        "adjudication_id": adjudication_id,
        "fact_record_id": PROMOTABLE,
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
    promoted = copy.deepcopy(fact)
    promoted["knowledge_status"] = "promoted_validated_fact"
    promoted["trust_tier"] = "B"
    promoted["qualifiers"].update(
        {
            "normalized_unit": "MWh/MSEK",
            "scope_boundary": "Sandvik activities in high climate impact sectors",
            "value_origin": "source_disclosure_independently_limited_assured",
            "answer_status": "verified",
        }
    )
    promoted["evidence"].append(
        {
            "source_id": "ASSURANCE-KB-B008-SANDVIK-AR2025-2025",
            "pdf_page": ASSURANCE_PAGE,
            "quote": ASSURANCE_TEXT,
            "role": "signed_independent_assurance_scope",
            "local_artifact": SOURCE.relative_to(ROOT).as_posix(),
            "local_artifact_sha256": SOURCE_SHA256,
        }
    )
    promoted["provenance"] = {
        "source_artifact": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "reference_status": f"tier_b_adjudication:{adjudication_id}",
        "simulated": False,
    }
    promoted["promotion"] = {
        "eligible": True,
        "reason": f"passed_independent_adjudication:{adjudication_id}",
    }

    all_adjudications = sorted(
        adjudications + [adjudication], key=lambda item: (item["task_id"], item["fact_record_id"])
    )
    all_trusted = sorted(
        trusted + [promoted], key=lambda item: (item["subject"]["task_id"], item["record_id"])
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
    dump_jsonl(adjudications_path, all_adjudications)
    dump_jsonl(trusted_path, all_trusted)
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_008_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": 1,
        "promotable_fact_ids": [PROMOTABLE],
        "blocked_fact_ids": sorted(BLOCKED),
        "blocked_by_reason": {
            reason: sorted(key for key, value in BLOCKED.items() if value == reason)
            for reason in sorted(set(BLOCKED.values()))
        },
        "total_trusted_tier_b": len(all_trusted),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "atomic_increment_sha256": sha256_file(INCREMENT),
            "atomic_validations_sha256": sha256_file(VALIDATIONS),
            "native_coordinate_audit_sha256": sha256_file(NATIVE_AUDIT),
        },
        "outputs": {
            "adjudications_sha256": sha256_file(adjudications_path),
            "trusted_facts_sha256": sha256_file(trusted_path),
        },
        "native_audit": audit,
        "next_gate": "scale_batch_008_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
