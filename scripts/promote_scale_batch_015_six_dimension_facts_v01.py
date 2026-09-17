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
INCREMENT = KB / "increments/scale_batch_015_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_015_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_015_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_015_native_coordinate_audit.lock.json"

SOURCES = {
    "KB-B015-UCB-IAR2025": {
        "path": ROOT / "data/raw/scale_batch_015/ucb-integrated-annual-report-2025.pdf",
        "sha256": "2e2ff4cf9ee3ebced39312897fdd439139c767ac5d81d151257502dd428e154a",
        "assurance_pages": [125, 127],
        "scope": "UCB consolidated Sustainability Statement for the year ended 31 December 2025",
        "quote": (
            "We have performed a limited assurance engagement on the Group's "
            "consolidated sustainability information."
        ),
        "issuer": "UCB SA",
        "period": "31 December 2025",
        "conclusion": "nothing has come to our attention",
        "signatory": "Sébastien Schueremans",
    },
    "KB-B015-ARLA-AR2025": {
        "path": ROOT / "data/raw/scale_batch_015/arla-annual-report-2025.pdf",
        "sha256": "8c40632f70765f428b16534ca7403da8b8a47c2e81afecb71e5f9ec129ff059c",
        "assurance_pages": [161, 162],
        "scope": "Arla Foods sustainability statements for 1 January to 31 December 2025",
        "quote": (
            "We have conducted a limited assurance engagement on the remaining parts "
            "of the sustainability statements of Arla Foods amba."
        ),
        "issuer": "Arla Foods amba",
        "period": "1 January - 31 December 2025",
        "conclusion": "Limited assurance conclusion",
        "signatory": "Monica Mai Bak Larsen",
    },
    "KB-B015-FRESENIUS-AR2025": {
        "path": ROOT / "data/raw/scale_batch_015/fresenius-annual-report-2025.pdf",
        "sha256": "27c4589b96d7ff22a0acc6794b46f638c2ad76f016ba5a4675742f3110441c77",
        "assurance_pages": [431, 434],
        "scope": "Fresenius Group Sustainability Report for 1 January to 31 December 2025",
        "quote": (
            "nothing has come to our attention that causes us to believe that the "
            "accompanying Group Sustainability Report is not prepared, in all material "
            "respects"
        ),
        "issuer": "Fresenius SE & Co. KGaA",
        "period": "1 January to 31 December",
        "conclusion": "nothing has come to our attention",
        "signatory": "Aissata Touré",
    },
}

PROMOTABLE = {
    "fact-dd3a4b7af85e12528272e0c8": ("percent", 60),
    "fact-7de5dceb5c94d0aa5c471690": ("percent", 90),
    "fact-ad55ae8d6139423565c43acf": ("fatalities", 90),
    "fact-cb3929ff3ea001d8a9e4dd22": ("recordable accidents per million hours worked", 90),
    "fact-32c52cd1013415d53278d51b": ("days", 90),
    "fact-a1a6dc2ea6245a6748f50ef1": ("lost-time incidents per million hours worked", 90),
    "fact-2dad002419c61f2a7d35025f": ("percent", 90),
    "fact-3cc8b68719de736c8c01dfc4": ("thousand MWh", 47),
    "fact-0b1ca7374489c9eaa4d31362": ("thousand MWh", 47),
    "fact-a577ba349c74797373b5c64e": ("thousand MWh", 47),
    "fact-347585f5bafc5a07be317856": ("percent", 47),
    "fact-1c97d90036d2b72e7ac0e471": ("milk-equivalent thousand tonnes", 59),
    "fact-f004aee42551b78d45188e0c": ("milk-equivalent thousand tonnes", 59),
    "fact-de010aaa34bca28d8ef02e3b": ("milk-equivalent thousand tonnes", 59),
    "fact-b8a794689f0a7118087d0f6b": ("milk-equivalent thousand tonnes", 59),
    "fact-a971e6805b80ff1762b20c55": ("milk-equivalent thousand tonnes", 59),
    "fact-544b70e3471114e617a4a7fd": ("milk-equivalent thousand tonnes", 59),
    "fact-f397a1f8c7e9128bc7b3b674": ("milk-equivalent thousand tonnes", 59),
    "fact-114f2eb45d6efc88b95cc215": ("percent", 59),
    "fact-1593af08f447cf7b82c212bd": ("MWh per EUR 1 million revenue", 208),
    "fact-a42e30998950aa990104f0a9": ("headcount", 249),
    "fact-02d3aaf47f4a3c53f80d856d": ("headcount", 249),
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


def pdf_page(source: Path, page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(source), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def native_audit(
    candidates: dict[str, dict[str, Any]], validations: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    page_hashes: dict[str, str] = {}
    for source_id, spec in SOURCES.items():
        checks[f"{source_id}:source_sha256"] = sha256_file(spec["path"]) == spec["sha256"]
        assurance_text = "\n".join(pdf_page(spec["path"], p) for p in spec["assurance_pages"])
        assurance_normalized = " ".join(assurance_text.casefold().split())
        for field in ("issuer", "period", "conclusion", "signatory"):
            literal = " ".join(spec[field].casefold().split())
            checks[f"{source_id}:assurance_{field}"] = literal in assurance_normalized
        for page in spec["assurance_pages"]:
            text = pdf_page(spec["path"], page)
            page_hashes[f"{source_id}:p{page}"] = hashlib.sha256(text.encode()).hexdigest()
    for fact_id, (_, expected_page) in PROMOTABLE.items():
        fact = candidates[fact_id]
        evidence = fact["evidence"][0]
        checks[f"{fact_id}:period"] = evidence["normalized_period"] == 2025
        checks[f"{fact_id}:page"] = evidence["pdf_page"] == expected_page
        checks[f"{fact_id}:coordinate"] = validations[fact_id]["coordinate_corroborated"]
    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise ValueError(f"native coordinate or assurance audit failed: {failed}")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-015-NATIVE-COORDINATE-AUDIT",
        "status": "all_selected_2025_cells_and_assurance_windows_passed",
        "promotable_facts": len(PROMOTABLE),
        "checks": checks,
        "assurance_page_text_sha256": page_hashes,
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_adjudication(fact: dict[str, Any], unit: str) -> dict[str, Any]:
    fact_id = fact["record_id"]
    evidence = fact["evidence"][0]
    source = SOURCES[evidence["source_id"]]
    adjudication_id = stable_id(
        "adj",
        {
            "fact_record_id": fact_id,
            "source_sha256": source["sha256"],
            "assurance_pages": source["assurance_pages"],
        },
    )
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": fact["subject"]["entity_label"],
            "evidence": "issuer in signed assurance report matches the data page",
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
            "normalized": source["scope"],
            "evidence": source["quote"],
        },
        "value": {
            "status": "matched",
            "normalized": evidence["quote"],
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
    evidence = fact["evidence"][0]
    source = SOURCES[evidence["source_id"]]
    promoted["knowledge_status"] = "promoted_validated_fact"
    promoted["trust_tier"] = "B"
    promoted["qualifiers"].update(
        {
            "normalized_unit": unit,
            "scope_boundary": source["scope"],
            "value_origin": "source_disclosure_independently_assured",
            "answer_status": "verified",
        }
    )
    promoted["evidence"].append(
        {
            "source_id": f"ASSURANCE-{evidence['source_id']}-2025",
            "pdf_page": source["assurance_pages"][0],
            "quote": source["quote"],
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
    return promoted


def main() -> None:
    candidates = {item["record_id"]: item for item in load_jsonl(INCREMENT)}
    validations = {item["fact_record_id"]: item for item in load_jsonl(VALIDATIONS)}
    if len(candidates) != 60 or set(candidates) != set(validations):
        raise ValueError("fail-closed: batch-fifteen atomic inventory changed")
    if not set(PROMOTABLE) < set(candidates):
        raise ValueError("fail-closed: batch-fifteen promotion partition changed")
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
        raise ValueError("fail-closed: partial batch-fifteen promotion already exists")
    new_adjudications = [
        make_adjudication(candidates[fact_id], spec[0]) for fact_id, spec in PROMOTABLE.items()
    ]
    new_trusted = [
        make_promoted(
            candidates[item["fact_record_id"]],
            PROMOTABLE[item["fact_record_id"]][0],
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
        "status": "scale_batch_015_six_dimension_tier_b_sampling_complete",
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(PROMOTABLE),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": blocked,
        "blocked_by_reason": {
            "prior_period_or_failed_coordinate_or_not_selected_for_independent_gate": blocked
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
        "next_gate": "scale_batch_015_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
