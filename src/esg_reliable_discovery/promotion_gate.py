from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .knowledge_base import sha256_file, stable_id
from .postvalidation_attachment import validate_postvalidation_attachment


def _is_numeric_fact(fact: dict[str, Any]) -> bool:
    value = fact.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return bool(re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?%?", str(value).strip()))


def _source_integrity(fact: dict[str, Any], root: Path) -> tuple[bool, list[str]]:
    metadata = fact.get("subject", {}).get("document_metadata") or []
    failures = []
    if not metadata:
        return False, ["SOURCE_METADATA_MISSING"]
    for item in metadata:
        relative = item.get("local_path")
        expected = item.get("sha256")
        if not relative or not expected:
            failures.append("SOURCE_PATH_OR_HASH_MISSING")
            continue
        path = root / relative
        if not path.is_file():
            failures.append("SOURCE_ARTIFACT_MISSING")
        elif sha256_file(path) != expected:
            failures.append("SOURCE_HASH_MISMATCH")
    return not failures, sorted(set(failures))


def evaluate_promotion_dry_run(
    fact: dict[str, Any], gap_signatures: list[str], root: Path
) -> dict[str, Any]:
    source_ok, source_reasons = _source_integrity(fact, root)
    evidence = fact.get("evidence") or []
    qualifiers = fact.get("qualifiers") or {}
    predicate = fact.get("predicate", {}).get("canonical_key", "")
    numeric = _is_numeric_fact(fact)
    calculated = predicate.startswith("calculated") or bool(
        qualifiers.get("calculation_expression")
    )

    dimensions = {
        "source_integrity": "passed" if source_ok else "blocked",
        "raw_evidence": (
            "passed"
            if evidence and all(str(item.get("quote", "")).strip() for item in evidence)
            else "blocked"
        ),
        "field_or_cell_binding": (
            "passed"
            if any(
                item.get("cell_handle")
                or item.get("coordinates")
                or all(key in item for key in ("row_index", "column_index", "pdf_page"))
                for item in evidence
            )
            else "blocked"
        ),
        "period_binding": (
            "passed"
            if qualifiers.get("reference_period") is not None
            else "blocked"
        ),
        "unit_binding": (
            "passed"
            if numeric and qualifiers.get("normalized_unit")
            else "not_required" if not numeric else "blocked"
        ),
        "scope_binding": (
            "passed" if qualifiers.get("scope_boundary") else "blocked"
        ),
        "conflict_clearance": (
            "blocked"
            if any("CONFLICT" in signature for signature in gap_signatures)
            else "passed"
        ),
        "calculation_lineage": (
            "not_required"
            if not calculated
            else "passed"
            if qualifiers.get("calculation_expression")
            and "CALCULATION_LINEAGE_INCOMPLETE" not in gap_signatures
            else "blocked"
        ),
        "independent_corroboration": (
            "passed"
            if not fact.get("provenance", {}).get("simulated", True)
            and any(
                "independent" in str(item.get("role", "")).casefold()
                or "assurance" in str(item.get("role", "")).casefold()
                for item in evidence
            )
            else "blocked"
        ),
    }
    reasons = list(source_reasons)
    reasons.extend(
        f"{name.upper()}_INCOMPLETE"
        for name, status in dimensions.items()
        if status == "blocked" and name != "source_integrity"
    )
    reasons.extend(f"OPEN_GAP:{signature}" for signature in sorted(set(gap_signatures)))
    reasons = sorted(set(reasons))
    eligible = not reasons
    identity = {
        "fact_record_id": fact["record_id"],
        "dimensions": dimensions,
        "gap_signatures": sorted(set(gap_signatures)),
    }
    return {
        "schema_version": "0.1",
        "record_kind": "supervised_promotion_gate_dry_run",
        "dry_run_id": stable_id("promotion-gate-dry-run", identity),
        "fact_record_id": fact["record_id"],
        "input_trust_tier": fact.get("trust_tier"),
        "decision": "eligible" if eligible else "blocked",
        "dimensions": dimensions,
        "blocking_reasons": reasons,
        "rollback_plan": {
            "action": "discard dry-run record",
            "fact_record_unchanged": True,
            "trusted_layer_unchanged": True,
        },
        "promotion_performed": False,
    }


def evaluate_promotion_dry_run_with_attachments(
    fact: dict[str, Any],
    gaps: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
    root: Path,
) -> dict[str, Any]:
    gaps_by_id = {gap["gap_id"]: gap for gap in gaps}
    valid = []
    rejected = []
    for attachment in attachments:
        gap = gaps_by_id.get(attachment.get("parent_gap_id"))
        if gap is None:
            rejected.append(
                {
                    "attachment_id": attachment.get("attachment_id"),
                    "reasons": ["ATTACHMENT_PARENT_GAP_NOT_FOUND"],
                }
            )
            continue
        reasons = validate_postvalidation_attachment(attachment, fact, gap, root)
        if reasons:
            rejected.append(
                {"attachment_id": attachment.get("attachment_id"), "reasons": reasons}
            )
        else:
            valid.append(attachment)

    satisfied_gap_ids = {item["parent_gap_id"] for item in valid}
    remaining_gaps = [gap for gap in gaps if gap["gap_id"] not in satisfied_gap_ids]
    result = evaluate_promotion_dry_run(
        fact, [gap["gap_signature"] for gap in remaining_gaps], root
    )
    for attachment in valid:
        for dimension in attachment["satisfied_dimensions"]:
            result["dimensions"][dimension] = "passed_by_postvalidation_attachment"
            result["blocking_reasons"] = [
                reason
                for reason in result["blocking_reasons"]
                if reason != f"{dimension.upper()}_INCOMPLETE"
            ]
    result["decision"] = "eligible" if not result["blocking_reasons"] else "blocked"
    result["attachments"] = {
        "accepted": [item["attachment_id"] for item in valid],
        "rejected": rejected,
    }
    result["promotion_performed"] = False
    return result
