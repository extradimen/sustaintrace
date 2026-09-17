from __future__ import annotations

import json
from collections import defaultdict
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
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/postvalidation_attachment_development_v0.1"
CASES = [
    {
        "fact_id": "fact-61bd8e9933b6241a59c78a43",
        "gap_id": "gap-5d08f89dd8ef48c157edf5c1",
        "diagnostic": (
            "artifacts/fourth_unseen_adapter_validation_v0.1/"
            "table_cell_binding_incomplete.unseen.json"
        ),
        "dimension": "field_or_cell_binding",
    },
    {
        "fact_id": "fact-dc5c3f556943596d742d6c29",
        "gap_id": "gap-9ebeb7dde64ca3eb9b96a21d",
        "diagnostic": (
            "artifacts/fourth_unseen_adapter_validation_v0.1/"
            "calculation_lineage_incomplete.unseen.json"
        ),
        "dimension": "calculation_lineage",
    },
]


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    summary_path = OUTPUT / "development_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_postvalidation_attachment_development")
    facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    gaps = {item["gap_id"]: item for item in _jsonl(GAPS)}
    gaps_by_fact = defaultdict(list)
    for gap in gaps.values():
        gaps_by_fact[gap["fact_record_id"]].append(gap)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for case in CASES:
        fact = facts[case["fact_id"]]
        gap = gaps[case["gap_id"]]
        attachment = build_postvalidation_attachment(
            fact=fact,
            gap=gap,
            diagnostic_path=case["diagnostic"],
            satisfied_dimensions=[case["dimension"]],
            remaining_dimensions=[],
            root=ROOT,
        )
        reasons = validate_postvalidation_attachment(attachment, fact, gap, ROOT)
        gate = evaluate_promotion_dry_run_with_attachments(
            fact, gaps_by_fact[fact["record_id"]], [attachment], ROOT
        )
        attachment_path = OUTPUT / f"{attachment['attachment_id']}.json"
        attachment_path.write_text(
            json.dumps(attachment, ensure_ascii=False, indent=2) + "\n"
        )
        records.append(
            {
                "fact_record_id": fact["record_id"],
                "gap_id": gap["gap_id"],
                "dimension": case["dimension"],
                "attachment_valid": not reasons,
                "attachment_accepted_by_gate": attachment["attachment_id"]
                in gate["attachments"]["accepted"],
                "final_gate_decision": gate["decision"],
                "remaining_blocking_reasons": gate["blocking_reasons"],
                "path": str(attachment_path.relative_to(ROOT)),
                "sha256": sha256_file(attachment_path),
            }
        )
    summary = {
        "schema_version": "0.1",
        "status": "postvalidation_attachment_development_complete",
        "records": records,
        "valid_attachments": sum(item["attachment_valid"] for item in records),
        "accepted_by_gate": sum(item["attachment_accepted_by_gate"] for item in records),
        "eligible_facts": sum(item["final_gate_decision"] == "eligible" for item in records),
        "fact_write_performed": False,
        "gap_mutation_performed": False,
        "trust_promotion_performed": False,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "valid": summary["valid_attachments"],
                "accepted": summary["accepted_by_gate"],
                "eligible": summary["eligible_facts"],
            }
        )
    )


if __name__ == "__main__":
    main()
