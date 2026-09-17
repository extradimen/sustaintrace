from __future__ import annotations

from typing import Any

from .v18_collection import project_grounded_collection


def project_composite_assurance_subjects(
    *, subjects: list[dict[str, str]], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project assurance subjects independently instead of one composite string."""
    if any(not item.get("assurance_level") for item in subjects):
        raise ValueError("v19_assurance_level_required_per_subject")
    projected = project_grounded_collection(members=subjects, evidence=evidence)
    projected["members"] = [
        {**member, "assurance_level": source["assurance_level"]}
        for member, source in zip(projected["members"], subjects, strict=True)
    ]
    projected["projection_rule"] = "independently_grounded_assurance_subjects"
    return projected
