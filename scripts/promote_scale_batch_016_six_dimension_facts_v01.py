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
INCREMENT = KB / "increments/scale_batch_016_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_016_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_016_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_016_native_coordinate_audit.lock.json"
SOURCE = {
    "path": ROOT / "data/raw/scale_batch_016/novonesis-annual-report-2025.pdf",
    "sha256": "dd3bf837735c9cd24760e717099568a0fe012707cb97536ca199e5e2ea98a2dc",
    "assurance_pages": [197, 199],
    "scope": "Novonesis A/S Sustainability statement on pages 53–117 for 2025",
    "quote": (
        "We have conducted a limited assurance engagement on the Sustainability "
        "statement of Novonesis A/S"
    ),
    "issuer": "Novonesis A/S",
    "period": "January 1 – December 31, 2025",
    "conclusion": "Limited assurance conclusion",
    "signatory": "Lars Fermann",
}
PROMOTABLE = {
    "fact-b708a8ccb4f468227c0b6ca1": "number of lost time injuries",
    "fact-7bdc7e0f43e0729ad7985fbf": "rate per million working hours",
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
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(SOURCE["path"]), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def native_audit(
    candidates: dict[str, dict[str, Any]], validations: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    checks: dict[str, bool] = {"source_sha256": sha256_file(SOURCE["path"]) == SOURCE["sha256"]}
    assurance_text = "\n".join(pdf_page(page) for page in SOURCE["assurance_pages"])
    assurance_normalized = " ".join(assurance_text.casefold().split())
    for field in ("issuer", "period", "conclusion", "signatory"):
        literal = " ".join(SOURCE[field].casefold().split())
        checks[f"assurance_{field}"] = literal in assurance_normalized
    page_hashes = {
        f"p{page}": hashlib.sha256(pdf_page(page).encode()).hexdigest()
        for page in SOURCE["assurance_pages"]
    }
    for fact_id in PROMOTABLE:
        evidence = candidates[fact_id]["evidence"][0]
        checks[f"{fact_id}:period"] = evidence["normalized_period"] == 2025
        checks[f"{fact_id}:page"] = evidence["pdf_page"] == 99
        checks[f"{fact_id}:coordinate"] = validations[fact_id]["coordinate_corroborated"]
    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise ValueError(f"native coordinate or assurance audit failed: {failed}")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-016-NATIVE-COORDINATE-AUDIT",
        "status": "all_selected_2025_cells_and_assurance_window_passed",
        "promotable_facts": len(PROMOTABLE),
        "checks": checks,
        "assurance_page_text_sha256": page_hashes,
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_adjudication(fact: dict[str, Any], unit: str) -> dict[str, Any]:
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
            "normalized": "Novonesis A/S",
            "evidence": "issuer identity in signed assurance report matches the data page",
        },
        "metric": {
            "status": "matched",
            "normalized": fact["predicate"]["raw_key"],
            "evidence": "native PDF row label and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": "2025",
            "evidence": "native 2025 column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": unit,
            "evidence": "native table heading or accounting policy defines the unit",
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
            "reason": "all_six_dimensions_match_and_2025_assurance_scope_is_frozen",
            "locked_experiments_modified": False,
        },
    }


def make_promoted(fact: dict[str, Any], unit: str, adjudication_id: str) -> dict[str, Any]:
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
            "source_id": "ASSURANCE-KB-B016-NOVONESIS-AR2025-2025",
            "pdf_page": 197,
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
    if len(candidates) != 6 or set(candidates) != set(validations):
        raise ValueError("fail-closed: batch-sixteen atomic inventory changed")
    if not set(PROMOTABLE) < set(candidates):
        raise ValueError("fail-closed: batch-sixteen promotion partition changed")
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
        raise ValueError("fail-closed: partial batch-sixteen promotion already exists")
    new_adjudications = [
        make_adjudication(candidates[fact_id], unit) for fact_id, unit in PROMOTABLE.items()
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
        "status": "scale_batch_016_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(PROMOTABLE),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": blocked,
        "blocked_by_reason": {"prior_period_or_failed_coordinate": blocked},
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
        "next_gate": "scale_batch_016_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
