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
INCREMENT = KB / "increments/scale_batch_014_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_014_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_014_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_014_native_coordinate_audit.lock.json"
SOURCE = ROOT / "data/raw/scale_batch_014/essity-annual-report-2025.pdf"
SOURCE_SHA256 = "95bb4e9968ebfe8350ad8bc6055f3fe5d204c2c53a23669cede94831559e63b7"
ASSURANCE_QUOTE = (
    "We have conducted a limited assurance engagement of the sustainability statement "
    "prepared by Essity Aktiebolag (publ) for the financial year 2025."
)
SCOPE = "Essity sustainability statement pages 47-99, financial year 2025"
PROMOTABLE = {
    "fact-d5e5528770cad188dbb0c583": {
        "metric": "Scope 1, from biofuel use",
        "value": "408",
        "unit": "kton CO2e",
    },
    "fact-1a9f7031feeda8ea1d27d5bd": {
        "metric": "Scope 2, from purchased steam",
        "value": "50",
        "unit": "kton CO2e",
    },
    "fact-dfdc89c6b5bd5783335e26cc": {
        "metric": "Employees in Germany",
        "value": "5,193",
        "unit": "headcount",
    },
    "fact-da410017dd65f4d1291afdcc": {
        "metric": "Employees in Mexico",
        "value": "4,140",
        "unit": "headcount",
    },
    "fact-99ebdba383b776ec594f87b6": {
        "metric": "Employees in Colombia",
        "value": "3,681",
        "unit": "headcount",
    },
    "fact-3cc992793a95be699f118ecd": {
        "metric": "Employees in other countries",
        "value": "23,361",
        "unit": "headcount",
    },
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


def pdf_page(page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(SOURCE), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def native_coordinate_audit(candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    emissions = pdf_page(68)
    workforce = pdf_page(82)
    assurance = pdf_page(184)
    signature = pdf_page(185)
    checks = {
        "source_sha256_matches": sha256_file(SOURCE) == SOURCE_SHA256,
        "emissions_table_unit_present": "GHG emissions, kton CO2e" in emissions,
        "emissions_rows_present": all(
            value in emissions
            for value in ("Scope 1, from biofuel use", "Scope 2, from purchased steam")
        ),
        "workforce_table_present": "Number of employees" in workforce,
        "workforce_reporting_basis_present": (
            "headcount" in workforce and "average of five quarters" in workforce
        ),
        "all_promotable_values_present": all(
            spec["value"] in (emissions if "CO2e" in spec["unit"] else workforce)
            for spec in PROMOTABLE.values()
        ),
        "assurance_issuer_present": "Essity Aktiebolag" in assurance,
        "assurance_period_present": "financial year 2025" in assurance,
        "assurance_statement_pages_present": "pages 47–99" in assurance,
        "assurance_conclusion_present": "Conclusion" in assurance,
        "assurance_signatory_present": "Erik Sandström" in signature,
        "all_frozen_coordinates_corroborated": all(
            item["checks"]["table_graph_coordinate_exact"]
            and item["coordinate_corroborated"]
            for item in candidates.values()
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"native coordinate or assurance audit failed: {checks}")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-014-NATIVE-COORDINATE-AUDIT",
        "status": "essity_2025_cells_passed_prior_periods_blocked",
        "document_id": "KB-B014-ESSITY-AR2025",
        "data_pages": [68, 82],
        "assurance_pages": [184, 185],
        "assurance_scope": SCOPE,
        "checks": checks,
        "native_page_sha256": {
            "68": hashlib.sha256(emissions.encode()).hexdigest(),
            "82": hashlib.sha256(workforce.encode()).hexdigest(),
            "184": hashlib.sha256(assurance.encode()).hexdigest(),
            "185": hashlib.sha256(signature.encode()).hexdigest(),
        },
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_adjudication(fact: dict[str, Any], spec: dict[str, str]) -> dict[str, Any]:
    fact_id = fact["record_id"]
    adjudication_id = stable_id(
        "adj",
        {"fact_record_id": fact_id, "source_sha256": SOURCE_SHA256, "assurance_pages": [184, 185]},
    )
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": "Essity Aktiebolag (publ)",
            "evidence": "issuer identity in signed assurance report matches the data pages",
        },
        "metric": {
            "status": "matched",
            "normalized": spec["metric"],
            "evidence": "native PDF row label and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": "2025",
            "evidence": "native 2025 column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": spec["unit"],
            "evidence": "native table heading or reporting basis states the unit",
        },
        "scope_boundary": {
            "status": "matched",
            "normalized": SCOPE,
            "evidence": ASSURANCE_QUOTE,
        },
        "value": {
            "status": "matched",
            "normalized": spec["value"],
            "evidence": "native PDF cell and frozen graph value match",
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


def make_promoted(
    fact: dict[str, Any], spec: dict[str, str], adjudication_id: str
) -> dict[str, Any]:
    promoted = copy.deepcopy(fact)
    promoted["knowledge_status"] = "promoted_validated_fact"
    promoted["trust_tier"] = "B"
    promoted["qualifiers"].update(
        {
            "normalized_unit": spec["unit"],
            "scope_boundary": SCOPE,
            "value_origin": "source_disclosure_independently_limited_assured",
            "answer_status": "verified",
        }
    )
    promoted["evidence"].append(
        {
            "source_id": "ASSURANCE-KB-B014-ESSITY-AR2025-2025",
            "pdf_page": 184,
            "quote": ASSURANCE_QUOTE,
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
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    validations = {item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)}
    if len(candidates) != 20 or set(candidates) != set(validations):
        raise ValueError("fail-closed: batch-fourteen atomic inventory changed")
    blocked = {
        fact_id: "comparative_or_prior_period_not_unambiguously_within_2025_assurance_scope"
        for fact_id in set(candidates) - set(PROMOTABLE)
    }
    if set(candidates) != set(PROMOTABLE) | set(blocked):
        raise ValueError("fail-closed: batch-fourteen promotion partition changed")
    audit = native_coordinate_audit(validations)
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
        raise ValueError("fail-closed: partial batch-fourteen promotion already exists")

    new_adjudications = [
        make_adjudication(candidates[fact_id], spec) for fact_id, spec in PROMOTABLE.items()
    ]
    new_trusted = [
        make_promoted(
            candidates[item["fact_record_id"]],
            PROMOTABLE[item["fact_record_id"]],
            item["adjudication_id"],
        )
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
        "status": "scale_batch_014_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(PROMOTABLE),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": sorted(blocked),
        "blocked_by_reason": {
            reason: sorted(key for key, value in blocked.items() if value == reason)
            for reason in sorted(set(blocked.values()))
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
        "next_gate": "scale_batch_014_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
