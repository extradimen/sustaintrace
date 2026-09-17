from __future__ import annotations

from typing import Any

from .v15_grounding import unicode_equivalent_substring


def project_grounded_string_fragments(
    *, fragments: list[dict[str, str]], evidence: list[dict[str, Any]],
    separator: str = " | ",
) -> dict[str, Any]:
    """Compose a string from independently grounded verbatim evidence fragments."""
    if not fragments:
        raise ValueError("v17_fragments_must_be_nonempty")
    index = {item["handle"]: item for item in evidence}
    if len(index) != len(evidence):
        raise ValueError("v17_evidence_handles_must_be_unique")
    preserved = []
    for position, fragment in enumerate(fragments, start=1):
        handle = fragment["evidence_handle"]
        verbatim = " ".join(fragment["verbatim_value"].split())
        if handle not in index:
            raise ValueError(f"v17_unknown_evidence_handle:{handle}")
        if not unicode_equivalent_substring(
            verbatim, index[handle].get("verbatim_text", "")
        ):
            raise ValueError(f"v17_fragment_not_grounded:{position}")
        preserved.append({
            "position":position,
            "evidence_handle":handle,
            "verbatim_value":verbatim,
        })
    return {
        "value":separator.join(item["verbatim_value"] for item in preserved),
        "fragments":preserved,
        "composition_rule":"ordered_verbatim_fragment_join",
        "separator":separator,
        "all_fragments_grounded":True,
        "candidate_text_rewritten":False,
    }
