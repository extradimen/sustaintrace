from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .knowledge_base import sha256_file, stable_id


def _semantic_key(fact: dict[str, Any]) -> tuple[Any, ...]:
    qualifiers = fact.get("qualifiers") or {}
    subject = fact.get("subject") or {}
    return (
        subject.get("entity_label"),
        fact.get("predicate", {}).get("canonical_key"),
        qualifiers.get("reference_period"),
        qualifiers.get("normalized_unit"),
        qualifiers.get("scope_boundary"),
    )


def _source_integrity(
    fact: dict[str, Any], workspace_root: Path
) -> tuple[bool, set[str]]:
    metadata = fact.get("subject", {}).get("document_metadata") or []
    registered_ids = {
        str(item)
        for item in fact.get("subject", {}).get("document_ids", [])
        if str(item).strip()
    }
    if not metadata:
        return False, registered_ids
    for item in metadata:
        source_id = item.get("source_id") or item.get("document_id")
        if source_id:
            registered_ids.add(str(source_id))
        path_literal = item.get("local_path")
        expected = item.get("sha256")
        if not path_literal or not expected:
            return False, registered_ids
        path = Path(path_literal)
        resolved = path if path.is_absolute() else workspace_root / path
        if not resolved.is_file() or sha256_file(resolved) != expected:
            return False, registered_ids
    return True, registered_ids


def _evidence_sources(fact: dict[str, Any]) -> tuple[set[str], bool]:
    evidence = fact.get("evidence") or []
    sources = {
        str(item["source_id"])
        for item in evidence
        if isinstance(item.get("source_id"), str) and item["source_id"].strip()
    }
    independent_role = any(
        "independent" in str(item.get("role", "")).casefold()
        or "assurance" in str(item.get("role", "")).casefold()
        for item in evidence
    )
    return sources, independent_role


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def stage_approved_promotion(
    *,
    review: dict[str, Any],
    fact: dict[str, Any],
    trusted_facts: list[dict[str, Any]],
    workspace_root: Path,
) -> dict[str, Any]:
    """Create a reversible overlay proposal; never mutate candidate or trusted layers."""
    sources, independent_role = _evidence_sources(fact)
    source_hashes_valid, registered_source_ids = _source_integrity(fact, workspace_root)
    evidence = fact.get("evidence") or []
    qualifiers = fact.get("qualifiers") or {}
    collisions = [item for item in trusted_facts if _semantic_key(item) == _semantic_key(fact)]
    equivalent = any(item.get("value") == fact.get("value") for item in collisions)
    conflict = any(item.get("value") != fact.get("value") for item in collisions)
    checks = {
        "review_approved_for_staging": review.get("state")
        == "approved_for_promotion_staging",
        "review_did_not_claim_promotion": review.get("promotion_performed") is False,
        "candidate_is_tier_c": fact.get("trust_tier") == "C",
        "source_hashes_valid": source_hashes_valid,
        "evidence_sources_registered": bool(sources)
        and sources <= registered_source_ids,
        "two_distinct_sources": len(sources) >= 2,
        "independent_or_assurance_role_present": independent_role,
        "raw_evidence_present": bool(evidence)
        and all(str(item.get("quote", "")).strip() for item in evidence),
        "field_or_cell_binding_present": any(
            item.get("cell_handle") or item.get("coordinates") for item in evidence
        ),
        "period_bound": qualifiers.get("reference_period") is not None,
        "unit_bound_when_numeric": (
            qualifiers.get("normalized_unit") is not None
            if _is_numeric(fact.get("value"))
            else True
        ),
        "scope_bound": bool(qualifiers.get("scope_boundary")),
        "controlled_conflict_clear": not conflict,
        "not_already_trusted_equivalent": not equivalent,
    }
    identity = {
        "review_id": review["review_id"],
        "fact_record_id": fact["record_id"],
        "review_version": review["version"],
        "semantic_key": _semantic_key(fact),
    }
    blocking_reasons = sorted(name for name, passed in checks.items() if not passed)
    if equivalent:
        state = "already_trusted_equivalent"
    elif blocking_reasons:
        state = "blocked_promotion_preconditions"
    else:
        state = "ready_for_tier_b_overlay_commit"

    proposed_overlay = None
    if state == "ready_for_tier_b_overlay_commit":
        proposed_overlay = deepcopy(fact)
        proposed_overlay["trust_tier"] = "B"
        proposed_overlay["knowledge_status"] = "trusted_overlay_staging"
        proposed_overlay["provenance"] = {
            **fact.get("provenance", {}),
            "promotion_staging_id": stable_id("workbench-promotion-staging", identity),
            "promotion_review_id": review["review_id"],
            "independent_source_ids": sorted(sources),
        }
        proposed_overlay["promotion"] = {
            "eligible": True,
            "reason": "all_controlled_staging_preconditions_passed",
            "committed": False,
        }

    return {
        "schema_version": "1.0",
        "record_kind": "workbench_promotion_staging",
        "staging_id": stable_id("workbench-promotion-staging", identity),
        "review_id": review["review_id"],
        "review_version": review["version"],
        "fact_record_id": fact["record_id"],
        "state": state,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "source_ids": sorted(sources),
        "trusted_collision_record_ids": sorted(
            item["record_id"] for item in collisions if item.get("record_id")
        ),
        "proposed_overlay": proposed_overlay,
        "promotion_performed": False,
        "trusted_layer_modified": False,
        "rollback_action": "delete job-local staging record and preserve Tier C candidate",
    }
