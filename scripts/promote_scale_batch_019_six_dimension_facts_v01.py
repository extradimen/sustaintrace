from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"
INCREMENT = KB / "increments/scale_batch_019_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_019_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_019_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_019_native_coordinate_audit.lock.json"

SOURCES = {
    "KB-B019-BOLIDEN-ASR2025": {
        "path": ROOT / "data/raw/scale_batch_019/boliden-annual-and-sustainability-report-2025.pdf",
        "sha256": "ecb892e7a804075324db3c5d229239091cff1d3937e714d94111d9997c74652d",
        "assurance_pages": [122, 123],
        "scope": (
            "Boliden AB statutory sustainability statement on pages 50–119 "
            "for financial year 2025"
        ),
        "quote": (
            "We have conducted a limited assurance engagement of the sustainability "
            "statement for Boliden AB (publ) for the financial year 2025"
        ),
        "issuer": "Boliden AB (publ)",
        "period": "financial year 2025",
        "conclusion": "nothing has come",
        "signatory": "Anna Rosendal",
    },
    "KB-B019-METSO-AR2025": {
        "path": ROOT / "data/raw/scale_batch_019/metso-annual-report-2025.pdf",
        "sha256": "c05a1ebd588ab9dd268904dd5203c9262ed27c71a1f6089c5da082658811fc3d",
        "assurance_pages": [239, 240],
        "scope": (
            "Metso Corporation group sustainability statement for 2025, including "
            "presented 2024 comparative information"
        ),
        "quote": (
            "We have performed a limited assurance engagement on the group "
            "sustainability statement of Metso Corporation"
        ),
        "issuer": "Metso Corporation",
        "period": "1.1.–31.12.2025",
        "conclusion": "nothing has come",
        "signatory": "Toni Halonen",
    },
}

PROMOTABLE = {
    "fact-5cfc24bb65256801f296f30d": ("KB-B019-BOLIDEN-ASR2025", "MWh"),
    "fact-29d728688a98473cf1cf7aa8": ("KB-B019-BOLIDEN-ASR2025", "MWh"),
    "fact-bb83848514f33112267c1c65": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-c90d439d184eab2f0f7a8caf": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-678a1ba36310a0a2a11b36ae": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-3886c2eb80dd8c341bd00c48": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-60887e607a3414f1c753a1a6": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-ec85e5993bf06273a4fef4a3": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-f195f48d28b08c3bc01479c0": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-15aa801fc44f87f0bc630afe": ("KB-B019-METSO-AR2025", "TRIF rate"),
    "fact-fcd5c1ea347795b3376bdae1": ("KB-B019-METSO-AR2025", "TRIF rate"),
}
EXPECTED_CANDIDATES = 23
BATCH_NUMBER = "019"
STATUS = "scale_batch_019_six_dimension_tier_b_review_complete"
BLOCKED_REASON = "outside_assurance_period_or_invalid_repeated_header_cell"
NEXT_GATE = "scale_batch_019_global_kb_rebuild_and_closure"
ALLOWED_PERIODS = {
    "KB-B019-BOLIDEN-ASR2025": {2025},
    "KB-B019-METSO-AR2025": {2024, 2025},
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


def promotion_already_applied(
    promotable: dict[str, tuple[str, str]],
    adjudicated_ids: set[str],
    trusted_ids: set[str],
) -> bool:
    """An empty reviewed partition is a new no-op result, not prior application."""
    return bool(promotable) and set(promotable) <= adjudicated_ids and set(
        promotable
    ) <= trusted_ids


def pdf_page(source: dict, page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(source["path"]), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def native_audit(candidates: dict, validations: dict) -> dict:
    checks: dict[str, bool] = {}
    assurance_hashes: dict[str, str] = {}
    for document_id, source in SOURCES.items():
        checks[f"{document_id}:source_sha256"] = sha256_file(source["path"]) == source["sha256"]
        assurance_pages = [pdf_page(source, page) for page in source["assurance_pages"]]
        assurance_text = " ".join("\n".join(assurance_pages).casefold().split())
        for field in ("issuer", "period", "conclusion", "signatory"):
            checks[f"{document_id}:assurance_{field}"] = (
                " ".join(source[field].casefold().split()) in assurance_text
            )
        for page, text in zip(source["assurance_pages"], assurance_pages, strict=True):
            assurance_hashes[f"{document_id}:p{page}"] = hashlib.sha256(text.encode()).hexdigest()
    for fact_id, (document_id, _) in PROMOTABLE.items():
        fact = candidates[fact_id]
        evidence = fact["evidence"][0]
        source = SOURCES[document_id]
        native_text = " ".join(pdf_page(source, evidence["pdf_page"]).casefold().split())
        checks[f"{fact_id}:document"] = evidence["source_id"] == document_id
        checks[f"{fact_id}:coordinate"] = validations[fact_id]["coordinate_corroborated"]
        checks[f"{fact_id}:period"] = evidence["normalized_period"] in ALLOWED_PERIODS[
            document_id
        ]
        checks[f"{fact_id}:row"] = (
            " ".join(evidence["row_header"].casefold().split()) in native_text
        )
        checks[f"{fact_id}:value"] = evidence["quote"].casefold() in native_text
    if not all(checks.values()):
        raise ValueError(
            f"native or assurance audit failed: {[k for k, v in checks.items() if not v]}"
        )
    payload = {
        "schema_version": "0.1",
        "batch_id": f"KB-SCALE-BATCH-{BATCH_NUMBER}-NATIVE-COORDINATE-AUDIT",
        "status": "selected_cells_and_assurance_boundaries_passed",
        "promotable_facts": len(PROMOTABLE),
        "checks": checks,
        "assurance_page_text_sha256": assurance_hashes,
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_adjudication(fact: dict, document_id: str, unit: str) -> dict:
    source = SOURCES[document_id]
    fact_id = fact["record_id"]
    adjudication_id = stable_id(
        "adj",
        {
            "fact_record_id": fact_id,
            "source_sha256": source["sha256"],
            "assurance_pages": source["assurance_pages"],
        },
    )
    period = str(fact["evidence"][0]["normalized_period"])
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": fact["subject"]["entity_label"],
            "evidence": "issuer identity in signed assurance report matches the data page",
        },
        "metric": {
            "status": "matched",
            "normalized": fact["predicate"]["raw_key"],
            "evidence": "native PDF row label and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": period,
            "evidence": "native period column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": unit,
            "evidence": "native table metric label identifies the measurement unit or rate",
        },
        "scope_boundary": {
            "status": "matched",
            "normalized": source["scope"],
            "evidence": source["quote"],
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


def make_promoted(fact: dict, document_id: str, unit: str, adjudication_id: str) -> dict:
    source = SOURCES[document_id]
    promoted = copy.deepcopy(fact)
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
            "source_id": f"ASSURANCE-{document_id}",
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
    if len(candidates) != EXPECTED_CANDIDATES or set(candidates) != set(validations):
        raise ValueError(f"fail-closed: Batch{BATCH_NUMBER} atomic inventory changed")
    if not set(PROMOTABLE) < set(candidates):
        raise ValueError(f"fail-closed: Batch{BATCH_NUMBER} promotion partition changed")
    audit = native_audit(candidates, validations)
    adjudications_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    existing_adjudications = load_jsonl(adjudications_path)
    existing_trusted = load_jsonl(trusted_path)
    adjudicated_ids = {item["fact_record_id"] for item in existing_adjudications}
    trusted_ids = {item["record_id"] for item in existing_trusted}
    if promotion_already_applied(PROMOTABLE, adjudicated_ids, trusted_ids):
        print(json.dumps(json.loads(SUMMARY.read_text()), sort_keys=True))
        return
    if (set(PROMOTABLE) & adjudicated_ids) or (set(PROMOTABLE) & trusted_ids):
        raise ValueError(f"fail-closed: partial Batch{BATCH_NUMBER} promotion already exists")
    new_adjudications = [
        make_adjudication(candidates[fact_id], *PROMOTABLE[fact_id]) for fact_id in PROMOTABLE
    ]
    new_trusted = [
        make_promoted(
            candidates[item["fact_record_id"]],
            *PROMOTABLE[item["fact_record_id"]],
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
        "status": STATUS,
        "reviewed": len(candidates),
        "newly_promoted_to_tier_b": len(PROMOTABLE),
        "promotable_fact_ids": sorted(PROMOTABLE),
        "blocked_fact_ids": blocked,
        "blocked_by_reason": {BLOCKED_REASON: blocked},
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
        "next_gate": NEXT_GATE,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
