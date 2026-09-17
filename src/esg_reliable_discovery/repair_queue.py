from __future__ import annotations

from collections import Counter
from typing import Any

from .knowledge_base import stable_id

REPAIR_LANES = {
    "PERIOD_ATTACHMENT_INCOMPLETE": {
        "queue_class": "deterministic_binding_screen",
        "execution_decision": "screen_not_executed",
        "validator_id": "RV-PERIOD-UNIQUE-COLUMN-V01",
        "invariants": [
            "one frozen cell column contains exactly one year",
            "period is copied without inference",
        ],
    },
    "UNIT_ATTACHMENT_INCOMPLETE": {
        "queue_class": "deterministic_binding_screen",
        "execution_decision": "screen_not_executed",
        "validator_id": "RV-UNIT-DUAL-SOURCE-MARKER-V01",
        "invariants": [
            "the same unit marker occurs in the bound quote and native source",
            "unit is copied without conversion",
        ],
    },
    "BOUNDARY_ATTACHMENT_INCOMPLETE": {
        "queue_class": "semantic_block",
        "execution_decision": "blocked",
        "validator_id": "RV-EXPLICIT-BOUNDARY-CLAUSE-V01",
        "invariants": [
            "an explicit caption note or boundary clause is required",
            "no boundary is inferred from task or document context",
        ],
    },
    "FIELD_EVIDENCE_BINDING_INCOMPLETE": {
        "queue_class": "read_only_diagnostic",
        "execution_decision": "read_only_not_executed",
        "validator_id": "RV-SOURCE-NATIVE-FIELD-BINDER-V01",
        "invariants": [
            "one field maps to one frozen evidence location",
            "ambiguous collections remain unresolved",
        ],
    },
    "TABLE_CELL_BINDING_INCOMPLETE": {
        "queue_class": "read_only_diagnostic",
        "execution_decision": "read_only_not_executed",
        "validator_id": "RV-TABLE-ROW-COLUMN-TOPOLOGY-V01",
        "invariants": [
            "row and column coordinates are both present",
            "native topology agrees with parser output",
        ],
    },
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": {
        "queue_class": "read_only_diagnostic",
        "execution_decision": "read_only_not_executed",
        "validator_id": "RV-NATIVE-PDF-CORROBORATION-V01",
        "invariants": [
            "source path and source hash are frozen",
            "numeric normalization preserves the native literal",
        ],
    },
    "CALCULATION_LINEAGE_INCOMPLETE": {
        "queue_class": "read_only_diagnostic",
        "execution_decision": "read_only_not_executed",
        "validator_id": "RV-CALCULATION-OPERATION-GRAPH-V01",
        "invariants": [
            "every operand points to a frozen input cell",
            "the operation graph is replayable without model inference",
        ],
    },
}


def build_second_repair_queue(
    *,
    gaps: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    gaps_sha256: str,
    rankings_sha256: str,
) -> list[dict[str, Any]]:
    ranking_index = {item["gap_signature"]: item for item in rankings}
    if len(ranking_index) != len(rankings):
        raise ValueError("duplicate_repair_gap_ranking")
    gap_ids = [item["gap_id"] for item in gaps]
    if len(set(gap_ids)) != len(gap_ids):
        raise ValueError("duplicate_knowledge_gap_id")

    records = []
    for gap in sorted(gaps, key=lambda item: item["gap_id"]):
        signature = gap["gap_signature"]
        lane = REPAIR_LANES.get(signature)
        ranking = ranking_index.get(signature)
        if lane is None or ranking is None:
            raise ValueError(f"unroutable_knowledge_gap:{signature}")
        identity = {
            "gap_id": gap["gap_id"],
            "gaps_sha256": gaps_sha256,
            "rankings_sha256": rankings_sha256,
            "validator_id": lane["validator_id"],
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "second_repair_queue_item",
                "queue_id": stable_id("repair-queue", identity),
                "gap_id": gap["gap_id"],
                "fact_record_id": gap["fact_record_id"],
                "task_id": gap["task_id"],
                "gap_signature": signature,
                "current_state": gap["current_state"],
                "required_state": gap["required_state"],
                "risk": ranking["risk"],
                "rank": ranking["rank"],
                "queue_class": lane["queue_class"],
                "execution_decision": lane["execution_decision"],
                "validator_id": lane["validator_id"],
                "expected_artifact": (
                    f"artifacts/second_repair_queue_v0.1/{gap['gap_id']}.json"
                ),
                "invariants": lane["invariants"],
                "rollback_action": "delete derived fixture and preserve the parent gap and fact",
                "parent_inputs": {
                    "knowledge_gaps": {
                        "path": "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl",
                        "sha256": gaps_sha256,
                    },
                    "repair_rankings": {
                        "path": "data/knowledge_bases/v0.1/repair_gap_rankings.jsonl",
                        "sha256": rankings_sha256,
                    },
                },
                "execution_performed": False,
                "semantic_repair_allowed": False,
            }
        )
    return records


def summarize_second_repair_queue(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "records": len(records),
        "signature_counts": dict(sorted(Counter(r["gap_signature"] for r in records).items())),
        "queue_class_counts": dict(sorted(Counter(r["queue_class"] for r in records).items())),
        "execution_decision_counts": dict(
            sorted(Counter(r["execution_decision"] for r in records).items())
        ),
        "risk_counts": dict(sorted(Counter(r["risk"] for r in records).items())),
    }
