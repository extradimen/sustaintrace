from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


POLICY = {
    "FIELD_EVIDENCE_BINDING_INCOMPLETE": (
        "medium",
        "read_only_plan",
        "build source-native field and collection binders before retrying qualification",
    ),
    "BOUNDARY_ATTACHMENT_INCOMPLETE": (
        "high",
        "blocked",
        "require explicit caption, note or boundary-clause attachment; no automatic inference",
    ),
    "TABLE_CELL_BINDING_INCOMPLETE": (
        "medium",
        "read_only_plan",
        "reconstruct row-column topology from native coordinates and cross-check parser output",
    ),
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": (
        "medium",
        "read_only_plan",
        "reconcile source paths, numeric normalization and native layout extraction",
    ),
    "PERIOD_ATTACHMENT_INCOMPLETE": (
        "low",
        "partially_executed",
        "continue only where one frozen cell column contains exactly one year",
    ),
    "UNIT_ATTACHMENT_INCOMPLETE": (
        "medium",
        "safe_path_exhausted",
        "require the same unit marker in the bound quote and native PDF or escalate",
    ),
    "CALCULATION_LINEAGE_INCOMPLETE": (
        "medium",
        "read_only_plan",
        "replace legacy expressions with frozen input cells and replayable operation graphs",
    ),
}


def main() -> None:
    gap_path = KB / "knowledge_gap_records.jsonl"
    native_path = KB / "native_pdf_corroborations.jsonl"
    period_path = KB / "period_attachment_repairs.jsonl"
    gaps = load(gap_path)
    native = {item["fact_record_id"]: item for item in load(native_path)}
    period_repaired = {item["fact_record_id"] for item in load(period_path)}
    by_signature = defaultdict(list)
    gap_count = Counter(item["fact_record_id"] for item in gaps)
    for gap in gaps:
        by_signature[gap["gap_signature"]].append(gap)
    draft = []
    for signature, items in by_signature.items():
        facts = {item["fact_record_id"] for item in items}
        executed = (
            len(facts & period_repaired) if signature == "PERIOD_ATTACHMENT_INCOMPLETE" else 0
        )
        remaining = len(items) - executed
        sole = sum(gap_count[fact_id] == 1 for fact_id in facts)
        strong = sum(
            native.get(fact_id, {}).get("status") == "passed_scalar_and_cell_labels"
            for fact_id in facts
        )
        risk, decision, action = POLICY[signature]
        risk_penalty = {"low": 0, "medium": 25, "high": 60}[risk]
        score = round(sole * 5 + strong * 3 + min(remaining, 500) / 50 - risk_penalty, 2)
        draft.append(
            {
                "schema_version": "0.1",
                "record_kind": "repair_gap_ranking",
                "rank": 0,
                "gap_signature": signature,
                "gap_records": len(items),
                "affected_facts": len(facts),
                "remaining_records": remaining,
                "sole_blocker_facts": sole,
                "native_strong_facts": strong,
                "risk": risk,
                "execution_decision": decision,
                "recommended_next_action": action,
                "score": score,
                "repairs_executed": executed,
            }
        )
    records = sorted(draft, key=lambda item: (-item["score"], item["gap_signature"]))
    for rank, item in enumerate(records, 1):
        item["rank"] = rank
    schema = json.loads(
        (ROOT / "schemas/knowledge/repair-gap-ranking-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output = KB / "repair_gap_rankings.jsonl"
    output.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    summary = {
        "schema_version": "0.1",
        "status": "risk_adjusted_repair_ranking_complete_no_new_execution",
        "ranked_signatures": len(records),
        "top_priority": records[0]["gap_signature"],
        "automatic_or_derived_actions_exhausted": [
            item["gap_signature"]
            for item in records
            if item["execution_decision"] in {"partially_executed", "safe_path_exhausted"}
        ],
        "new_repairs_executed": 0,
        "inputs": {
            "gaps_sha256": sha256_file(gap_path),
            "native_sha256": sha256_file(native_path),
            "period_repairs_sha256": sha256_file(period_path),
        },
        "output": {"path": output.relative_to(ROOT).as_posix(), "sha256": sha256_file(output)},
        "next_gate": "implement read-only fact query interface and source-native field binder",
    }
    summary_path = KB / "repair_gap_ranking_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"top": summary["top_priority"], "ranked": len(records)}))


if __name__ == "__main__":
    main()
