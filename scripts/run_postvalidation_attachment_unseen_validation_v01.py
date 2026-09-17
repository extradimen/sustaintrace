from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.postvalidation_attachment import (
    build_postvalidation_attachment,
    validate_postvalidation_attachment,
)
from esg_reliable_discovery.promotion_gate import (
    evaluate_promotion_dry_run_with_attachments,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/postvalidation_attachment_unseen_validation_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/postvalidation_attachment_unseen_validation_v0.1"


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    summary_path = OUTPUT / "validation_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_attachment_unseen_validation")
    manifest = json.loads(MANIFEST.read_text())
    case = manifest["case"]
    if sha256_file(ROOT / case["diagnostic"]["path"]) != case["diagnostic"]["sha256"]:
        raise ValueError("diagnostic_hash_mismatch_before_execution")
    if sha256_file(ROOT / case["source"]["path"]) != case["source"]["sha256"]:
        raise ValueError("source_hash_mismatch_before_execution")
    facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    all_gaps = _jsonl(GAPS)
    gaps = [item for item in all_gaps if item["fact_record_id"] == case["fact_record_id"]]
    gap = next(item for item in gaps if item["gap_id"] == case["gap_id"])
    fact = facts[case["fact_record_id"]]
    attachment = build_postvalidation_attachment(
        fact=fact,
        gap=gap,
        diagnostic_path=case["diagnostic"]["path"],
        satisfied_dimensions=case["satisfied_dimensions"],
        remaining_dimensions=[],
        root=ROOT,
    )
    reasons = validate_postvalidation_attachment(attachment, fact, gap, ROOT)
    gate = evaluate_promotion_dry_run_with_attachments(fact, gaps, [attachment], ROOT)
    expected = case["expected"]
    checks = {
        "attachment_valid": (not reasons) == expected["attachment_valid"],
        "attachment_accepted_by_gate": (
            attachment["attachment_id"] in gate["attachments"]["accepted"]
        )
        == expected["attachment_accepted_by_gate"],
        "final_gate_decision": gate["decision"] == expected["final_gate_decision"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    attachment_path = OUTPUT / "postvalidation_attachment.unseen.json"
    attachment_path.write_text(json.dumps(attachment, ensure_ascii=False, indent=2) + "\n")
    result = {
        "schema_version": "0.1",
        "status": "postvalidation_attachment_unseen_validation_complete",
        "contract_passed": all(checks.values()),
        "checks": checks,
        "validation_reasons": reasons,
        "gate_result": gate,
        "attachment_path": str(attachment_path.relative_to(ROOT)),
        "attachment_sha256": sha256_file(attachment_path),
        "fact_write_performed": False,
        "gap_mutation_performed": False,
        "trust_promotion_performed": False,
        "cloud_transmission_performed": False,
    }
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"contract_passed": result["contract_passed"]}))


if __name__ == "__main__":
    main()
