from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.postvalidation_attachment import (
    GAP_DIMENSIONS,
    build_postvalidation_attachment,
    validate_postvalidation_attachment,
)
from esg_reliable_discovery.promotion_gate import (
    evaluate_promotion_dry_run_with_attachments,
)

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / (
    "artifacts/heterogeneous_component_validation_v0.1/validation_summary.lock.json"
)
MANIFEST = ROOT / (
    "data/manifests/heterogeneous_component_validation_RESUME01_v0.1.lock.json"
)
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/heterogeneous_postvalidation_attachments_RESUME01_v0.1"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    summary_path = OUTPUT / "attachment_gate_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_heterogeneous_attachments")
    validation = json.loads(VALIDATION.read_text())
    manifest = json.loads(MANIFEST.read_text())
    cases = {item["case_id"]: item for item in manifest["cases"]}
    facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    all_gaps = _jsonl(GAPS)
    gaps_by_id = {item["gap_id"]: item for item in all_gaps}
    gaps_by_fact: dict[str, list[dict]] = {}
    for gap in all_gaps:
        gaps_by_fact.setdefault(gap["fact_record_id"], []).append(gap)

    OUTPUT.mkdir(parents=True, exist_ok=False)
    classifications = []
    attachments = []
    gates = []
    for item in validation["records"]:
        case = cases[item["case_id"]]
        path = ROOT / item["path"]
        payload = json.loads(path.read_text())
        observed = payload.get("observed", {})
        reason = None
        if not item["contract_passed"]:
            reason = "contract_failed"
        elif item["polarity"] != "positive":
            reason = "negative_contract_has_no_positive_dimension_claim"
        elif observed.get("status") != "passed":
            reason = "diagnostic_result_not_in_passed_attachment_interface_shape"
        elif case["gap_id"] not in gaps_by_id:
            reason = "parent_gap_not_registered"

        if reason:
            classifications.append(
                {
                    "case_id": item["case_id"],
                    "component": item["component"],
                    "attachment_applicable": False,
                    "reason": reason,
                }
            )
            continue

        gap = gaps_by_id[case["gap_id"]]
        fact = facts[case["fact_record_id"]]
        dimensions = sorted(GAP_DIMENSIONS[gap["gap_signature"]])
        remaining = sorted(
            {
                dimension
                for other in gaps_by_fact.get(fact["record_id"], [])
                if other["gap_id"] != gap["gap_id"]
                for dimension in GAP_DIMENSIONS.get(other["gap_signature"], set())
            }
        )
        attachment = build_postvalidation_attachment(
            fact=fact,
            gap=gap,
            diagnostic_path=item["path"],
            satisfied_dimensions=dimensions,
            remaining_dimensions=remaining,
            root=ROOT,
        )
        validation_reasons = validate_postvalidation_attachment(
            attachment, fact, gap, ROOT
        )
        attachment_path = OUTPUT / f"{item['case_id'].lower()}.attachment.json"
        attachment_path.write_text(
            json.dumps(attachment, ensure_ascii=False, indent=2) + "\n"
        )
        gate = evaluate_promotion_dry_run_with_attachments(
            fact, gaps_by_fact[fact["record_id"]], [attachment], ROOT
        )
        gate_path = OUTPUT / f"{item['case_id'].lower()}.gate.json"
        gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n")
        accepted = attachment["attachment_id"] in gate["attachments"]["accepted"]
        classifications.append(
            {
                "case_id": item["case_id"],
                "component": item["component"],
                "attachment_applicable": True,
                "attachment_valid": not validation_reasons,
                "attachment_accepted_by_gate": accepted,
            }
        )
        attachments.append(
            {
                "case_id": item["case_id"],
                "path": str(attachment_path.relative_to(ROOT)),
                "sha256": sha256_file(attachment_path),
            }
        )
        gates.append(
            {
                "case_id": item["case_id"],
                "decision": gate["decision"],
                "blocking_reasons": gate["blocking_reasons"],
                "path": str(gate_path.relative_to(ROOT)),
                "sha256": sha256_file(gate_path),
            }
        )

    summary = {
        "schema_version": "0.1",
        "record_kind": "heterogeneous_postvalidation_attachment_gate_summary",
        "status": "heterogeneous_postvalidation_attachment_gate_complete",
        "validation_parent": {
            "path": str(VALIDATION.relative_to(ROOT)),
            "sha256": sha256_file(VALIDATION),
        },
        "resume_lineage": {
            "parent": (
                "artifacts/heterogeneous_postvalidation_attachments_v0.1/"
                "attachment_gate_summary.lock.json"
            ),
            "parent_sha256": sha256_file(
                ROOT
                / "artifacts/heterogeneous_postvalidation_attachments_v0.1/"
                "attachment_gate_summary.lock.json"
            ),
            "reason": (
                "initial postprocessor read parent fact and gap IDs from the case "
                "result top level instead of the frozen manifest"
            ),
            "component_validation_reexecuted": False,
        },
        "classifications": classifications,
        "attachments": attachments,
        "gate_results": gates,
        "counts": {
            "validation_cases": len(validation["records"]),
            "contract_passed": validation["passed"],
            "attachments_applicable": len(attachments),
            "attachments_valid": sum(
                item.get("attachment_valid", False) for item in classifications
            ),
            "attachments_accepted": sum(
                item.get("attachment_accepted_by_gate", False)
                for item in classifications
            ),
            "final_gate_eligible": sum(
                item["decision"] == "eligible" for item in gates
            ),
        },
        "safety": {
            "fact_write_performed": False,
            "gap_mutation_performed": False,
            "trust_promotion_performed": False,
            "cloud_transmission_performed": False,
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary["counts"]))


if __name__ == "__main__":
    main()
