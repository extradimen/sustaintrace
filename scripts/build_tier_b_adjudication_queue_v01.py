from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    fact_path = KB / "fact_records.jsonl"
    native_path = KB / "source_native_field_bindings.jsonl"
    gap_path = KB / "knowledge_gap_records.jsonl"
    policy_path = ROOT / "configs/knowledge/tier_b_independent_source_policy_v0.1.json"
    facts = {item["record_id"]: item for item in load_jsonl(fact_path)}
    gaps: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in load_jsonl(gap_path):
        gaps[item["fact_record_id"]].append(item)

    records = []
    for native in load_jsonl(native_path):
        if native["status"] != "unique_context_binding":
            continue
        fact = facts[native["fact_record_id"]]
        blockers = sorted(
            {
                item["gap_signature"]
                for item in gaps.get(fact["record_id"], [])
                if item["gap_signature"] != "NATIVE_PDF_CORROBORATION_INCOMPLETE"
            }
        )
        ready = not blockers
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_adjudication_queue_item",
                "fact_record_id": fact["record_id"],
                "task_id": fact["subject"]["task_id"],
                "document_ids": fact["subject"].get("document_ids", []),
                "predicate": fact["predicate"]["canonical_key"],
                "value": fact["value"],
                "source_native_status": native["status"],
                "qualification_blockers": blockers,
                "independent_source_required": True,
                "independent_source_present": False,
                "adjudication_status": (
                    "ready_for_independent_source_review"
                    if ready
                    else "blocked_additional_qualification"
                ),
                "priority": 1 if ready else 2 + len(blockers),
                "promotion_eligible": False,
                "reason": (
                    "source_location_is_unique_but_an_independent_source_is_still_required"
                    if ready
                    else "qualification_gaps_must_be_resolved_before_independent_source_review"
                ),
            }
        )
    records.sort(key=lambda item: (item["priority"], item["task_id"], item["fact_record_id"]))

    schema_path = ROOT / "schemas/knowledge/tier-b-adjudication-queue-v0.1.schema.json"
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "tier_b_adjudication_queue.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts = Counter(item["adjudication_status"] for item in records)
    blocker_counts = Counter(
        blocker for item in records for blocker in item["qualification_blockers"]
    )
    summary = {
        "schema_version": "0.1",
        "status": "tier_b_adjudication_queue_complete_no_promotion",
        "records": len(records),
        "counts": dict(sorted(counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "independent_sources_present": 0,
        "promoted_to_tier_b": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "facts_sha256": sha256_file(fact_path),
            "source_native_bindings_sha256": sha256_file(native_path),
            "knowledge_gaps_sha256": sha256_file(gap_path),
            "independent_source_policy_sha256": sha256_file(policy_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "obtain and freeze policy-eligible independent corroboration for the six ready facts"
        ),
    }
    summary_path = KB / "tier_b_adjudication_queue_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
