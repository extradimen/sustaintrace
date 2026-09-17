from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .knowledge_base import sha256_file
from .postvalidation_attachment import GAP_DIMENSIONS


def _load_jsonl_index(path: Path, key: str) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    with path.open() as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            value = record.get(key)
            if value is None:
                raise ValueError(f"missing_{key}:{path}:{line_number}")
            records.setdefault(str(value), []).append(record)
    return records


def assess_diagnostic_parent_binding(
    *,
    fact_record_id: str,
    gap_id: str,
    requested_signature: str,
    satisfied_dimensions: list[str],
    fact_store_path: Path,
    gap_store_path: Path,
) -> dict[str, Any]:
    """Fail closed unless a requested diagnostic has immutable registered parents."""
    facts = _load_jsonl_index(fact_store_path, "record_id")
    gaps = _load_jsonl_index(gap_store_path, "gap_id")
    fact_matches = facts.get(fact_record_id, [])
    gap_matches = gaps.get(gap_id, [])
    reasons: list[str] = []

    if not fact_matches:
        reasons.append("PARENT_FACT_NOT_REGISTERED")
    elif len(fact_matches) != 1:
        reasons.append("PARENT_FACT_NOT_UNIQUE")
    if not gap_matches:
        reasons.append("PARENT_GAP_NOT_REGISTERED")
    elif len(gap_matches) != 1:
        reasons.append("PARENT_GAP_NOT_UNIQUE")

    gap = gap_matches[0] if len(gap_matches) == 1 else None
    if gap is not None:
        if gap.get("fact_record_id") != fact_record_id:
            reasons.append("PARENT_GAP_FACT_MISMATCH")
        if gap.get("gap_signature") != requested_signature:
            reasons.append("PARENT_GAP_SIGNATURE_MISMATCH")

    requested_dimensions = set(satisfied_dimensions)
    allowed_dimensions = GAP_DIMENSIONS.get(requested_signature)
    if (
        not requested_dimensions
        or allowed_dimensions is None
        or not requested_dimensions <= allowed_dimensions
    ):
        reasons.append("REQUESTED_DIMENSION_UNAUTHORIZED")

    return {
        "schema_version": "0.1",
        "record_kind": "diagnostic_parent_binding_preflight",
        "status": "blocked" if reasons else "passed",
        "blocking_reasons": sorted(set(reasons)),
        "requested": {
            "fact_record_id": fact_record_id,
            "gap_id": gap_id,
            "gap_signature": requested_signature,
            "satisfied_dimensions": sorted(requested_dimensions),
        },
        "resolved": {
            "fact_record": fact_matches[0] if len(fact_matches) == 1 else None,
            "gap_record": gap,
        },
        "immutable_stores": {
            "facts": {"path": str(fact_store_path), "sha256": sha256_file(fact_store_path)},
            "gaps": {"path": str(gap_store_path), "sha256": sha256_file(gap_store_path)},
        },
        "parent_records_modified": False,
    }


def run_preflighted_read_only_diagnostic(
    *,
    fixture: dict[str, Any],
    satisfied_dimensions: list[str],
    root: Path,
    fact_store_path: Path,
    gap_store_path: Path,
    diagnostic_runner: (
        Callable[[dict[str, Any], dict[str, Any], Path], dict[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    """Run a diagnostic exactly once only after immutable-parent preflight passes."""
    preflight = assess_diagnostic_parent_binding(
        fact_record_id=fixture["fact_record_id"],
        gap_id=fixture["gap_id"],
        requested_signature=fixture["gap_signature"],
        satisfied_dimensions=satisfied_dimensions,
        fact_store_path=fact_store_path,
        gap_store_path=gap_store_path,
    )
    if preflight["status"] != "passed":
        return {
            "schema_version": "0.1",
            "record_kind": "preflighted_read_only_diagnostic_execution",
            "status": "blocked_before_execution",
            "adapter_invocation_count": 0,
            "preflight": preflight,
            "diagnostic": None,
            "parent_records_modified": False,
        }

    if diagnostic_runner is None:
        from .read_only_diagnostics import run_read_only_diagnostic

        diagnostic_runner = run_read_only_diagnostic
    fact = preflight["resolved"]["fact_record"]
    diagnostic = diagnostic_runner(fixture, fact, root)
    return {
        "schema_version": "0.1",
        "record_kind": "preflighted_read_only_diagnostic_execution",
        "status": "completed",
        "adapter_invocation_count": 1,
        "preflight": preflight,
        "diagnostic": diagnostic,
        "parent_records_modified": False,
    }
