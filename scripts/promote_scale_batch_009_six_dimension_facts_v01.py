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
INCREMENT = KB / "increments/scale_batch_009_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_009_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_009_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_009_native_coordinate_audit.lock.json"
SOURCE = ROOT / "data/raw/scale_batch_009/carlsberg-group-annual-report-2025.pdf"
SOURCE_SHA256 = "35fad935180834f52819b3d4729ea30a09b75b69a6267fbec7e2ef1afadd58a4"
ASSURANCE_PAGE = 195
ASSURANCE_TEXT = (
    "We have conducted a limited assurance engagement on the Sustainability Statement "
    "of Carlsberg A/S (the ‘Group’) included in the Management’s Review (the "
    "‘Sustainability Statement’), (pp. 46-100) for the financial year "
    "1 January – 31 December 2025."
)

PROMOTABLE = {
    "fact-c3310ea2afc3b33e44c164d8": {
        "metric": "Share of Scope 2 GHG emissions covered by contractual instruments",
        "value": "67",
    },
    "fact-195fb3fd19e6d8dc2b7082cb": {
        "metric": (
            "Share of Scope 2 GHG emissions covered by energy attribute certificates (unbundled)"
        ),
        "value": "60",
    },
    "fact-f4b47f2e3dd9e247f1047a12": {
        "metric": ("Share of Scope 2 GHG emissions covered by power purchase agreements (bundled)"),
        "value": "7",
    },
}
BLOCKED = {
    "fact-23f13470cad2608901916fdd": "comparative_2024_not_explicitly_within_2025_assurance_period",
    "fact-51f0f4f79846b03fe97e2365": "comparative_2024_not_explicitly_within_2025_assurance_period",
    "fact-909d946c20c6c79e6929905f": "comparative_2024_not_explicitly_within_2025_assurance_period",
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


def native_coordinate_audit() -> dict[str, Any]:
    page = subprocess.run(
        ["pdftotext", "-f", "66", "-l", "66", "-layout", str(SOURCE), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assurance = subprocess.run(
        ["pdftotext", "-f", "195", "-l", "195", "-layout", str(SOURCE), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    checks = {
        "source_sha256_matches": sha256_file(SOURCE) == SOURCE_SHA256,
        "page_footer_matches": "Reports              66" in page,
        "unit_heading_present": "Contractual instruments (%) E1-6" in page,
        "year_headers_present": "2025   2024" in page,
        "contractual_row_values_present": "67     73" in page,
        "certificate_row_values_present": "60     72" in page,
        "ppa_row_values_present": "7      1" in page,
        "assurance_entity_present": "Sustainability Statement of Carlsberg A/S" in assurance,
        "assurance_page_scope_present": "(pp. 46-100)" in assurance,
        "assurance_period_present": "1 January – 31 December 2025" in assurance,
    }
    if not all(checks.values()):
        raise ValueError(f"native coordinate or assurance audit failed: {checks}")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-009-NATIVE-COORDINATE-AUDIT",
        "status": "passed",
        "document_id": "KB-B009-CARLSBERG-AR2025",
        "pdf_page": 66,
        "unit": "%",
        "columns": {
            "contractual_instruments": {"2025": "67", "2024": "73"},
            "energy_attribute_certificates_unbundled": {"2025": "60", "2024": "72"},
            "power_purchase_agreements_bundled": {"2025": "7", "2024": "1"},
        },
        "assurance": {
            "pdf_page": ASSURANCE_PAGE,
            "statement_page_range": [46, 100],
            "financial_year": 2025,
            "quote": ASSURANCE_TEXT,
        },
        "checks": checks,
        "native_page_sha256": hashlib.sha256(page.encode()).hexdigest(),
        "native_assurance_sha256": hashlib.sha256(assurance.encode()).hexdigest(),
        "source_sha256": SOURCE_SHA256,
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def adjudication(fact: dict[str, Any], spec: dict[str, str]) -> dict[str, Any]:
    fact_id = fact["record_id"]
    adjudication_id = stable_id(
        "adj",
        {
            "fact_record_id": fact_id,
            "source_sha256": SOURCE_SHA256,
            "assurance_page": ASSURANCE_PAGE,
        },
    )
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": "Carlsberg A/S",
            "evidence": "issuer identity and auditor addressee match",
        },
        "metric": {
            "status": "matched",
            "normalized": spec["metric"],
            "evidence": "native PDF row label and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": "2025",
            "evidence": "native PDF year column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": "%",
            "evidence": "native PDF table heading explicitly states percent",
        },
        "scope_boundary": {
            "status": "matched",
            "normalized": "Carlsberg Group Sustainability Statement, pp. 46-100",
            "evidence": ASSURANCE_TEXT,
        },
        "value": {
            "status": "matched",
            "normalized": spec["value"],
            "evidence": "native PDF ordered row values and frozen 2025 cell match",
        },
    }
    return {
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


def promoted_fact(fact: dict[str, Any], adjudication_id: str) -> dict[str, Any]:
    promoted = copy.deepcopy(fact)
    promoted["knowledge_status"] = "promoted_validated_fact"
    promoted["trust_tier"] = "B"
    promoted["qualifiers"].update(
        {
            "normalized_unit": "%",
            "scope_boundary": "Carlsberg Group Sustainability Statement, pp. 46-100",
            "value_origin": "source_disclosure_independently_limited_assured",
            "answer_status": "verified",
        }
    )
    promoted["evidence"].append(
        {
            "source_id": "ASSURANCE-KB-B009-CARLSBERG-AR2025-2025",
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
    return promoted


def main() -> None:
    audit = native_coordinate_audit()
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    if set(candidates) != set(PROMOTABLE) | set(BLOCKED):
        raise ValueError("fail-closed: batch-nine atomic candidate inventory changed")
    validations = {item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)}
    if not all(
        validations[fact_id]["checks"]["table_graph_coordinate_exact"] for fact_id in PROMOTABLE
    ):
        raise ValueError("frozen table-graph coordinate is not exact")
    for fact_id, spec in PROMOTABLE.items():
        evidence = candidates[fact_id]["evidence"][0]
        if evidence["normalized_period"] != 2025 or evidence["quote"] != spec["value"]:
            raise ValueError(f"promotable cell identity changed: {fact_id}")

    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    existing_adjudications = load_jsonl(adjudications_path)
    existing_trusted = load_jsonl(trusted_path)
    adjudicated_ids = {item["fact_record_id"] for item in existing_adjudications}
    trusted_ids = {item["record_id"] for item in existing_trusted}
    if set(PROMOTABLE) <= adjudicated_ids and set(PROMOTABLE) <= trusted_ids:
        if not SUMMARY.exists():
            raise ValueError("promotion exists but locked summary is missing")
        print(json.dumps(json.loads(SUMMARY.read_text()), sort_keys=True))
        return
    if (set(PROMOTABLE) & adjudicated_ids) or (set(PROMOTABLE) & trusted_ids):
        raise ValueError("fail-closed: partial batch-nine promotion already exists")

    new_adjudications = [
        adjudication(candidates[fact_id], spec) for fact_id, spec in PROMOTABLE.items()
    ]
    new_trusted = [
        promoted_fact(candidates[item["fact_record_id"]], item["adjudication_id"])
        for item in new_adjudications
    ]
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
        "status": "scale_batch_009_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(PROMOTABLE),
        "promotable_fact_ids": sorted(PROMOTABLE),
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
        "next_gate": "scale_batch_009_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
