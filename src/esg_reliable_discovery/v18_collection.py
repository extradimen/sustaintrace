from __future__ import annotations

from typing import Any

from .v17_multifragment import project_grounded_string_fragments


def project_grounded_collection(
    *, members: list[dict[str, str]], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project non-contiguous collection members with one audit trail per member."""
    if not members:
        raise ValueError("v18_collection_must_be_nonempty")
    identities = [item["canonical_id"] for item in members]
    if len(identities) != len(set(identities)):
        raise ValueError("v18_duplicate_canonical_member")
    projected = project_grounded_string_fragments(
        fragments=[
            {
                "evidence_handle": item["evidence_handle"],
                "verbatim_value": item["verbatim_value"],
            }
            for item in members
        ],
        evidence=evidence,
    )
    return {
        "members": [
            {"canonical_id": member["canonical_id"], **fragment}
            for member, fragment in zip(members, projected["fragments"], strict=True)
        ],
        "canonical_ids": identities,
        "member_count": len(members),
        "all_members_grounded": True,
        "candidate_output_modified": False,
    }
