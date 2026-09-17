from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_base import sha256_file, stable_id

DIAGNOSTIC_SHAPES = {
    "FIELD_EVIDENCE_BINDING_INCOMPLETE": [
        "field_id",
        "collection_cardinality",
        "evidence_coordinates",
        "unique_binding",
        "blocking_reasons",
    ],
    "TABLE_CELL_BINDING_INCOMPLETE": [
        "page",
        "row_header",
        "column_header",
        "cell_value",
        "cell_coordinates",
        "parser_native_agreement",
    ],
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": [
        "page",
        "source_literal",
        "parser_literal",
        "normalized_literal",
        "literal_agreement",
        "layout_agreement",
    ],
    "CALCULATION_LINEAGE_INCOMPLETE": [
        "input_cells",
        "operation_graph",
        "replay_output",
        "disclosed_value",
        "difference",
        "replay_status",
    ],
}


def _valid_source(path: Path, expected_sha256: str | None) -> tuple[bool, str]:
    if not path.is_file():
        return False, "source_file_missing"
    if expected_sha256 and sha256_file(path) != expected_sha256:
        return False, "source_sha256_mismatch"
    return True, "valid"


def select_exposed_fixture(
    *,
    signature: str,
    gaps: list[dict[str, Any]],
    facts: dict[str, dict[str, Any]],
    queue_items: dict[str, dict[str, Any]],
    root: Path,
    parent_hashes: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if signature not in DIAGNOSTIC_SHAPES:
        raise ValueError(f"unsupported_fixture_signature:{signature}")
    attempts = []
    candidates = sorted(
        (item for item in gaps if item["gap_signature"] == signature),
        key=lambda item: item["gap_id"],
    )
    for gap in candidates:
        reasons = []
        fact = facts.get(gap["fact_record_id"])
        queue_item = queue_items.get(gap["gap_id"])
        if fact is None:
            reasons.append("parent_fact_missing")
        if queue_item is None:
            reasons.append("queue_item_missing")
        source_path = None
        native_path = None
        if fact is not None:
            source_path = fact.get("provenance", {}).get("source_artifact")
            if not isinstance(source_path, str):
                reasons.append("source_artifact_path_missing")
            else:
                valid, reason = _valid_source(
                    root / source_path, fact.get("provenance", {}).get("source_sha256")
                )
                if not valid:
                    reasons.append(reason)
            metadata = fact.get("subject", {}).get("document_metadata", [])
            paths = [item for item in metadata if isinstance(item.get("local_path"), str)]
            if len(paths) != 1:
                reasons.append("unique_native_source_path_missing")
            else:
                native_path = paths[0]["local_path"]
                valid, reason = _valid_source(root / native_path, paths[0].get("sha256"))
                if not valid:
                    reasons.append(f"native_{reason}")
        attempts.append(
            {
                "gap_id": gap["gap_id"],
                "fact_record_id": gap["fact_record_id"],
                "decision": "selected" if not reasons else "blocked",
                "blocking_reasons": reasons,
            }
        )
        if reasons:
            continue
        identity = {
            "gap_id": gap["gap_id"],
            "fact_record_id": fact["record_id"],
            "signature": signature,
            "parent_hashes": parent_hashes,
        }
        fixture = {
            "schema_version": "0.1",
            "record_kind": "exposed_read_only_repair_fixture",
            "fixture_id": stable_id("repair-fixture", identity),
            "status": "prepared_not_executed",
            "gap_signature": signature,
            "gap_id": gap["gap_id"],
            "fact_record_id": fact["record_id"],
            "task_id": gap["task_id"],
            "queue_id": queue_item["queue_id"],
            "validator_id": queue_item["validator_id"],
            "source_artifact": {
                "path": source_path,
                "sha256": sha256_file(root / source_path),
            },
            "native_source": {
                "path": native_path,
                "sha256": sha256_file(root / native_path),
            },
            "evidence_pages": sorted(
                {
                    item["pdf_page"]
                    for item in fact.get("evidence", [])
                    if isinstance(item.get("pdf_page"), int)
                }
            ),
            "source_literals": [item.get("quote") for item in fact.get("evidence", [])],
            "diagnostic_contract": {
                "required_fields": DIAGNOSTIC_SHAPES[signature],
                "output_status": "pending_read_only_diagnostic",
                "semantic_inference_allowed": False,
                "fact_write_allowed": False,
                "trust_promotion_allowed": False,
            },
            "parent_hashes": parent_hashes,
            "rollback": {
                "action": "delete derived diagnostic fixture and preserve all parents",
                "parent_gap_preserved": True,
                "parent_fact_preserved": True,
            },
            "execution_performed": False,
            "historical_output_modified": False,
        }
        return fixture, attempts
    raise ValueError(f"no_auditable_fixture_candidate:{signature}")
