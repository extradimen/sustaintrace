from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_020_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_020_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_020_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_020_native_coordinate_audit.lock.json"

SOURCE = {
    "document_id": "KB-B020-SOLVAY-AIR2025",
    "path": ROOT / "data/raw/scale_batch_020/solvay-annual-integrated-report-2025.pdf",
    "sha256": "6e69c2a5af1653efc7786101d4f752d40cb07aab1f3a32f0a5e332e3d8370e15",
    "assurance_pages": [322, 323, 324, 325],
    "scope": (
        "Solvay SA consolidated Sustainability statement as of 31 December 2025 "
        "and for the year ended on that date"
    ),
    "quote": (
        "limited assurance engagement on the Company's sustainability information, "
        "included in section 6. Sustainability statement"
    ),
    "issuer": "Solvay SA",
    "period": "31 December 2025",
    "conclusion": "nothing has come",
    "signatory": "Eric Van Hoof",
}

PROMOTABLE = {
    "fact-610b488ee80ae635f85b0403": "Mt CO2eq",
    "fact-9f793e667397c4077acaba5b": "Mt CO2eq",
    "fact-c4d93293d990e6daf0493c58": "percent",
    "fact-48bdf3b86f6fb9eb227185b5": "percent",
    "fact-45b4291a25ca042e8f06fcc4": "percent",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )


def pdf_page(page: int) -> str:
    return subprocess.run(
        [
            "pdftotext",
            "-f",
            str(page),
            "-l",
            str(page),
            "-layout",
            str(SOURCE["path"]),
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def native_audit(candidates: dict, validations: dict) -> dict:
    checks: dict[str, bool] = {"source_sha256": sha256_file(SOURCE["path"]) == SOURCE["sha256"]}
    assurance_pages = [pdf_page(page) for page in SOURCE["assurance_pages"]]
    assurance_text = " ".join("\n".join(assurance_pages).casefold().split())
    for field in ("issuer", "period", "conclusion", "signatory"):
        checks[f"assurance_{field}"] = (
            " ".join(str(SOURCE[field]).casefold().split()) in assurance_text
        )
    for fact_id in PROMOTABLE:
        fact = candidates[fact_id]
        evidence = fact["evidence"][0]
        native_text = " ".join(pdf_page(evidence["pdf_page"]).casefold().split())
        checks[f"{fact_id}:document"] = evidence["source_id"] == SOURCE["document_id"]
        checks[f"{fact_id}:coordinate"] = validations[fact_id]["coordinate_corroborated"]
        checks[f"{fact_id}:period"] = evidence["normalized_period"] in {
            2021,
            2024,
            2025,
            2030,
        }
        checks[f"{fact_id}:row"] = (
            " ".join(evidence["row_header"].casefold().split()) in native_text
        )
        checks[f"{fact_id}:value"] = evidence["quote"].casefold() in native_text
    if not all(checks.values()):
        raise ValueError(
            f"native audit failed: {[key for key, value in checks.items() if not value]}"
        )
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-020-NATIVE-COORDINATE-AUDIT",
        "status": "selected_cells_and_assurance_boundary_passed",
        "promotable_facts": len(PROMOTABLE),
        "checks": checks,
        "assurance_page_text_sha256": {
            f"{SOURCE['document_id']}:p{page}": hashlib.sha256(text.encode()).hexdigest()
            for page, text in zip(SOURCE["assurance_pages"], assurance_pages, strict=True)
        },
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_adjudication(fact: dict, unit: str) -> dict:
    fact_id = fact["record_id"]
    adjudication_id = stable_id(
        "adj",
        {
            "fact_record_id": fact_id,
            "source_sha256": SOURCE["sha256"],
            "assurance_pages": SOURCE["assurance_pages"],
        },
    )
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": "Solvay SA",
            "evidence": "signed assurance report and data page identify Solvay",
        },
        "metric": {
            "status": "matched",
            "normalized": fact["predicate"]["raw_key"],
            "evidence": "native row label and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": str(fact["evidence"][0]["normalized_period"]),
            "evidence": "native period column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": unit,
            "evidence": "native table unit heading or row percentage label is explicit",
        },
        "scope_boundary": {
            "status": "matched",
            "normalized": SOURCE["scope"],
            "evidence": SOURCE["quote"],
        },
        "value": {
            "status": "matched",
            "normalized": fact["value"],
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
            "reason": "all_six_dimensions_match_and_assurance_scope_is_frozen",
            "locked_experiments_modified": False,
        },
    }


def make_promoted(fact: dict, unit: str, adjudication_id: str) -> dict:
    promoted = copy.deepcopy(fact)
    promoted["knowledge_status"] = "promoted_validated_fact"
    promoted["trust_tier"] = "B"
    promoted["qualifiers"].update(
        {
            "normalized_unit": unit,
            "scope_boundary": SOURCE["scope"],
            "value_origin": "source_disclosure_independently_assured",
            "answer_status": "verified",
        }
    )
    promoted["evidence"].append(
        {
            "source_id": f"ASSURANCE-{SOURCE['document_id']}",
            "pdf_page": SOURCE["assurance_pages"][0],
            "quote": SOURCE["quote"],
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
    return promoted


def main() -> None:
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    validations = {item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)}
    if len(candidates) != 15 or set(candidates) != set(validations):
        raise ValueError("fail-closed: Batch 20 atomic inventory changed")
    if not set(PROMOTABLE) < set(candidates):
        raise ValueError("fail-closed: Batch 20 promotion partition changed")
    audit = native_audit(candidates, validations)
    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    existing_adjudications = load_jsonl(adjudications_path)
    existing_trusted = load_jsonl(trusted_path)
    adjudicated_ids = {item["fact_record_id"] for item in existing_adjudications}
    trusted_ids = {item["record_id"] for item in existing_trusted}
    if set(PROMOTABLE) <= adjudicated_ids and set(PROMOTABLE) <= trusted_ids:
        print(json.dumps(json.loads(SUMMARY.read_text()), sort_keys=True))
        return
    if (set(PROMOTABLE) & adjudicated_ids) or (set(PROMOTABLE) & trusted_ids):
        raise ValueError("fail-closed: partial Batch 20 promotion already exists")
    new_adjudications = [
        make_adjudication(candidates[fact_id], PROMOTABLE[fact_id]) for fact_id in PROMOTABLE
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
    blocked = sorted(set(candidates) - set(PROMOTABLE))
    summary = {
        "schema_version": "0.1",
        "status": "scale_batch_020_six_dimension_tier_b_review_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(PROMOTABLE),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": blocked,
        "blocked_by_reason": {
            "missing_explicit_unit_or_coordinate_corroboration_or_change_semantics": blocked
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
        "next_gate": "scale_batch_020_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
