from __future__ import annotations

from typing import Any

from .v18_collection import project_grounded_collection


def project_collection_slot(
    *,
    slot_id: str,
    predicate_id: str,
    value_type: str,
    value: list[dict[str, Any]] | dict[str, dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project every array/object member into an independently grounded claim."""
    if value_type == "array":
        if not isinstance(value, list):
            raise ValueError(f"v20_collection_type_mismatch:{slot_id}:array")
        members = value
    elif value_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"v20_collection_type_mismatch:{slot_id}:object")
        members = [
            {"canonical_id": key, **member}
            for key, member in value.items()
        ]
    else:
        raise ValueError(f"v20_not_a_collection_slot:{slot_id}:{value_type}")
    projected = project_grounded_collection(members=members, evidence=evidence)
    claims = []
    for member in projected["members"]:
        claims.append(
            {
                "claim_id": f"{slot_id}::{member['canonical_id']}",
                "slot_id": slot_id,
                "predicate_id": predicate_id,
                "member_id": member["canonical_id"],
                "evidence_handle": member["evidence_handle"],
                "verbatim_value": member["verbatim_value"],
                "independently_grounded": True,
            }
        )
    return {
        "slot_id": slot_id,
        "value_type": value_type,
        "atomic_claims": claims,
        "atomic_claim_count": len(claims),
        "all_members_grounded": True,
        "candidate_output_modified": False,
    }
