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
INCREMENT = KB / "increments/scale_batch_010_atomic_fact_records.jsonl"
VALIDATIONS = KB / "increments/scale_batch_010_atomic_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_010_tier_b_promotion.lock.json"
NATIVE_AUDIT = ROOT / "data/results/scale_batch_010_native_coordinate_audit.lock.json"
VEOLIA_SOURCE = ROOT / "data/raw/scale_batch_010/veolia-universal-registration-document-2025.pdf"
VEOLIA_SHA256 = "09786eaedb20a992123e4b0f0d3c0f3484529ddf6093465c93251a0ce691232c"
PUMA_SOURCE = ROOT / "data/raw/scale_batch_010/puma-annual-report-2025.pdf"
PUMA_SHA256 = "d376e7dc2454df73f0750285e2cba255dc9ad05d61faa1aa5d508eb16991e13e"
ASSURANCE_PAGE = 328
ASSURANCE_TEXT = (
    "This report covers the sustainability information relating to the year ended "
    "December 31, 2025, included in the Group management report and presented in "
    "Section 4.1, ‘Sustainability Statement’ of the Universal Registration Document."
)
PROMOTABLE = {
    "fact-c894b332d64457a386649468": {"metric": "Biogenic Scope 1", "value": "6.7"},
    "fact-df1719c398059d112b1b3323": {"metric": "Biogenic Scope 2", "value": "0.1"},
    "fact-cf99175ab8dbae1bea8b6832": {"metric": "Biogenic Scope 3", "value": "7.6"},
}
BLOCKED_VEOLIA = {
    "fact-154d9691456040fc8653ee92": "comparative_2024_not_explicitly_within_2025_assurance_period",
    "fact-3cf3c63aacede12c1832c0bb": "comparative_2024_not_explicitly_within_2025_assurance_period",
}
BLOCKED_PUMA = {
    fact_id: "assurance_translation_period_internal_contradiction_2025_vs_2024"
    for fact_id in (
        "fact-e2781d7b06f88ad79e7d6426",
        "fact-3a817a9350253b3e33067bb5",
        "fact-36afda17a66a242d595b4000",
        "fact-9ba264baa2cb5d3f65c26156",
        "fact-08add829a959a0d421f73b02",
        "fact-0ce6f12a76d1445465524452",
        "fact-791400540be76465596965e1",
        "fact-47882664089fe4d9419dc9a8",
        "fact-70cadcb619889d6b5d15f0ee",
        "fact-0b69755c02fbbb00177b2e28",
        "fact-af18e851b490e3a7d3e4ea66",
        "fact-33e9cc8bc1cba535af275d8a",
    )
}
BLOCKED = BLOCKED_VEOLIA | BLOCKED_PUMA


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


def native_coordinate_audit() -> dict[str, Any]:
    veolia_page = pdf_page(VEOLIA_SOURCE, 219)
    veolia_assurance = pdf_page(VEOLIA_SOURCE, ASSURANCE_PAGE)
    puma_assurance = pdf_page(PUMA_SOURCE, 350)
    checks = {
        "veolia_source_sha256_matches": sha256_file(VEOLIA_SOURCE) == VEOLIA_SHA256,
        "puma_source_sha256_matches": sha256_file(PUMA_SOURCE) == PUMA_SHA256,
        "veolia_page_footer_matches": "DOCUMENT 2025                                      217"
        in veolia_page,
        "veolia_biogenic_heading_present": "Biogenic emissions" in veolia_page,
        "veolia_year_headers_present": "Result 2024             Result 2025" in veolia_page,
        "veolia_scope_1_values_present": "5.8                     6.7" in veolia_page,
        "veolia_scope_2_values_present": "0.2                     0.1" in veolia_page,
        "veolia_scope_3_current_value_present": "7.6" in veolia_page,
        "veolia_assurance_entity_present": "statutory auditors of Veolia" in veolia_assurance,
        "veolia_assurance_period_present": "ended December 31, 2025" in veolia_assurance,
        "veolia_assurance_section_present": "Section 4.1, “Sustainability Statement”"
        in veolia_assurance,
        "puma_main_assurance_period_2025_present": "January 1 to December 31, 2025"
        in puma_assurance,
        "puma_footnote_period_2024_present": "Group Sustainability Statement 2024"
        in puma_assurance,
    }
    if not all(checks.values()):
        raise ValueError(f"native coordinate or assurance audit failed: {checks}")
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-010-NATIVE-COORDINATE-AUDIT",
        "status": "veolia_passed_puma_fail_closed_on_assurance_period_contradiction",
        "veolia": {
            "document_id": "KB-B010-VEOLIA-URD2025",
            "pdf_page": 219,
            "unit": "Mt eq. CO2",
            "columns": {
                "scope_1": {"2024": "5.8", "2025": "6.7"},
                "scope_2": {"2024": "0.2", "2025": "0.1"},
                "scope_3": {"2024": "not disclosed", "2025": "7.6"},
            },
            "assurance_pdf_page": ASSURANCE_PAGE,
            "assurance_quote": ASSURANCE_TEXT,
        },
        "puma": {
            "document_id": "KB-B010-PUMA-AR2025",
            "assurance_pdf_page": 350,
            "promotion_blocker": (
                "main text says financial year 2025 while translation footnote says "
                "the engagement related to Group Sustainability Statement 2024"
            ),
        },
        "checks": checks,
        "native_veolia_page_sha256": hashlib.sha256(veolia_page.encode()).hexdigest(),
        "native_veolia_assurance_sha256": hashlib.sha256(veolia_assurance.encode()).hexdigest(),
        "native_puma_assurance_sha256": hashlib.sha256(puma_assurance.encode()).hexdigest(),
        "policy": {"cloud_transmission": False, "automatic_promotion": False},
    }
    NATIVE_AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_adjudication(fact: dict[str, Any], spec: dict[str, str]) -> dict[str, Any]:
    fact_id = fact["record_id"]
    adjudication_id = stable_id(
        "adj",
        {
            "fact_record_id": fact_id,
            "source_sha256": VEOLIA_SHA256,
            "assurance_page": ASSURANCE_PAGE,
        },
    )
    dimensions = {
        "entity": {
            "status": "matched",
            "normalized": "Veolia Environnement S.A.",
            "evidence": "issuer identity and statutory-auditor addressee match",
        },
        "metric": {
            "status": "matched",
            "normalized": spec["metric"],
            "evidence": "native PDF row label and frozen table graph match",
        },
        "period": {
            "status": "matched",
            "normalized": "2025",
            "evidence": "native Result 2025 column and frozen cell coordinate match",
        },
        "unit": {
            "status": "matched",
            "normalized": "Mt eq. CO2",
            "evidence": "native PDF row labels explicitly state the unit",
        },
        "scope_boundary": {
            "status": "matched",
            "normalized": "Veolia Section 4.1 Sustainability Statement",
            "evidence": ASSURANCE_TEXT,
        },
        "value": {
            "status": "matched",
            "normalized": spec["value"],
            "evidence": "native PDF row values and frozen 2025 cell match",
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


def make_promoted(fact: dict[str, Any], adjudication_id: str) -> dict[str, Any]:
    promoted = copy.deepcopy(fact)
    promoted["knowledge_status"] = "promoted_validated_fact"
    promoted["trust_tier"] = "B"
    promoted["qualifiers"].update(
        {
            "normalized_unit": "Mt eq. CO2",
            "scope_boundary": "Veolia Section 4.1 Sustainability Statement",
            "value_origin": "source_disclosure_independently_limited_assured",
            "answer_status": "verified",
        }
    )
    promoted["evidence"].append(
        {
            "source_id": "ASSURANCE-KB-B010-VEOLIA-URD2025-2025",
            "pdf_page": ASSURANCE_PAGE,
            "quote": ASSURANCE_TEXT,
            "role": "signed_independent_assurance_scope",
            "local_artifact": VEOLIA_SOURCE.relative_to(ROOT).as_posix(),
            "local_artifact_sha256": VEOLIA_SHA256,
        }
    )
    promoted["provenance"] = {
        "source_artifact": VEOLIA_SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": VEOLIA_SHA256,
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
        raise ValueError("fail-closed: batch-ten atomic candidate inventory changed")
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
        raise ValueError("fail-closed: partial batch-ten promotion already exists")

    new_adjudications = [
        make_adjudication(candidates[fact_id], spec) for fact_id, spec in PROMOTABLE.items()
    ]
    new_trusted = [
        make_promoted(candidates[item["fact_record_id"]], item["adjudication_id"])
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
        "status": "scale_batch_010_six_dimension_tier_b_sampling_complete",
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
        "next_gate": "scale_batch_010_global_kb_rebuild_and_closure",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
